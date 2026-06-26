import asyncio
import re
import time
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.query import Query, QueryResult, RetrievedChunk as RetrievedChunkModel
from app.rag.citation_validator import validate_citations
from app.rag.context_builder import build_context
from app.rag.generator import generate, generate_answer_stream, GenerationResult
from app.rag.hallucination_checker import check_hallucination
from app.rag.query_understanding import analyze_query
from app.rag.reranker import rerank
from app.rag.retriever import hybrid_retrieve, RetrievedChunk
from app.services.knowledge_gap_service import record_knowledge_gap
from app.services.verified_answer_service import match_verified_answer
from app.utils.costs import calculate_embedding_cost, calculate_llm_cost, calculate_rerank_cost
from app.utils.tokens import count_tokens

logger = structlog.get_logger()


async def process_query(
    query: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    session_id: uuid.UUID | None = None,
    workspace_name: str = "your organization",
) -> dict:
    timings: dict[str, int] = {}
    total_start = time.perf_counter()

    query_record = Query(
        workspace_id=workspace_id,
        user_id=user_id,
        original_query=query,
        session_id=session_id or uuid.uuid4(),
    )
    db.add(query_record)
    await db.flush()

    try:
        # Stage 0: verified-answer shortcut — if an admin-approved answer matches
        # this question, serve it directly (skip retrieval/generation; zero cost).
        t0 = time.perf_counter()
        match = await match_verified_answer(db, workspace_id, query)
        timings["verified_lookup_ms"] = int((time.perf_counter() - t0) * 1000)
        if match:
            va, score = match
            return await _save_verified_answer(db, query_record, va, score, timings, total_start)

        # Stage 1: Query understanding
        t0 = time.perf_counter()
        analysis = analyze_query(query)
        timings["query_understanding_ms"] = int((time.perf_counter() - t0) * 1000)

        search_query = analysis.rewritten_query
        query_record.rewritten_query = search_query
        query_record.query_type = analysis.query_type
        query_record.intent = analysis.intent
        query_record.metadata_filters = analysis.metadata_filters

        retrieval_filters = await _validate_filters(
            db, workspace_id, analysis.metadata_filters, query_text=query
        )

        # Stage 2: Hybrid retrieval
        t0 = time.perf_counter()
        retrieved = await hybrid_retrieve(
            search_query, workspace_id, db,
            top_k=settings.RETRIEVAL_TOP_K,
            filters=retrieval_filters,
            date_sensitive=analysis.date_sensitive,
        )
        timings["retrieval_ms"] = int((time.perf_counter() - t0) * 1000)

        if not retrieved:
            # Retry without filters if query understanding filters were too strict
            if retrieval_filters:
                logger.info("pipeline.retry_without_filters")
                t0 = time.perf_counter()
                retrieved = await hybrid_retrieve(
                    search_query, workspace_id, db,
                    top_k=settings.RETRIEVAL_TOP_K,
                    date_sensitive=analysis.date_sensitive,
                )
                timings["retrieval_ms"] += int((time.perf_counter() - t0) * 1000)

        if not retrieved:
            return await _save_no_answer(db, query_record, timings, total_start)

        # Stage 3: Reranking
        t0 = time.perf_counter()
        ranked = rerank(search_query, retrieved, top_k=settings.RERANK_TOP_K)
        timings["rerank_ms"] = int((time.perf_counter() - t0) * 1000)

        # Stage 4: Context construction (with conflict detection + staleness)
        t0 = time.perf_counter()
        context_result = build_context(ranked, token_budget=settings.CONTEXT_TOKEN_BUDGET)
        timings["context_build_ms"] = int((time.perf_counter() - t0) * 1000)

        if not context_result.formatted_context.strip():
            return await _save_no_answer(db, query_record, timings, total_start)

        # Stage 5: Generation
        t0 = time.perf_counter()
        gen_result = generate(query, context_result.formatted_context, workspace_name)
        timings["generation_ms"] = int((time.perf_counter() - t0) * 1000)

        # Stages 6 & 7: citation validation + hallucination check both run on the
        # same generated answer, independently. Run them concurrently (in threads,
        # since the LLM clients are sync) instead of sequentially — saves ~one
        # LLM round-trip of latency with zero change to the results.
        (citation_validation, cv_ms), (hallucination_result, hc_ms) = await asyncio.gather(
            _timed(
                validate_citations,
                gen_result.answer,
                gen_result.citations_used,
                context_result.chunks_used,
            ),
            _timed(
                check_hallucination,
                gen_result.answer,
                context_result.formatted_context,
            ),
        )
        timings["citation_validation_ms"] = cv_ms
        timings["hallucination_check_ms"] = hc_ms

        timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)

        # Apply hallucination threshold actions
        answer = gen_result.answer
        if hallucination_result.action == "block":
            answer = (
                "I was unable to generate a fully reliable answer. "
                "Here are the most relevant sources I found:\n\n"
                + "\n".join(
                    f"- {c.document_title}: {c.content[:150]}..."
                    for c in context_result.chunks_used[:5]
                )
            )
        elif hallucination_result.action == "disclaimer":
            if not answer.endswith("\n"):
                answer += "\n"
            if hallucination_result.verification_failed:
                answer += "\nNote: This answer could not be automatically verified against the sources. Please double-check important details."
            else:
                answer += "\nNote: Some statements in this answer may not be fully supported by the available sources."

        # Add staleness warning
        if context_result.stale_sources:
            sources_str = ", ".join(context_result.stale_sources[:3])
            answer += f"\n\nNote: Some information comes from potentially outdated sources ({sources_str}). Please verify with the latest documentation."

        query_tokens = count_tokens(query)
        validation_cost = calculate_llm_cost(
            citation_validation.prompt_tokens + hallucination_result.prompt_tokens,
            citation_validation.completion_tokens + hallucination_result.completion_tokens,
            model="gpt-4o-mini",
        )
        qu_cost = calculate_llm_cost(
            analysis.prompt_tokens, analysis.completion_tokens, model="gpt-4o-mini"
        )
        cost = _calculate_total_cost(query_tokens, len(retrieved), gen_result) + validation_cost + qu_cost

        citations = _build_citations(gen_result, context_result.chunks_used)

        status = "success"
        if hallucination_result.action == "block":
            status = "low_confidence"
        elif gen_result.confidence < 0.6:
            status = "low_confidence"

        result_record = QueryResult(
            query_id=query_record.id,
            answer=answer,
            confidence_score=gen_result.confidence,
            faithfulness_score=hallucination_result.faithfulness_score,
            hallucination_score=hallucination_result.hallucination_score,
            citation_accuracy=citation_validation.citation_accuracy,
            latency_ms=timings["total_ms"],
            latency_breakdown=timings,
            token_usage={
                "prompt_tokens": gen_result.prompt_tokens,
                "completion_tokens": gen_result.completion_tokens,
                "total_tokens": gen_result.total_tokens,
            },
            cost_usd=cost,
            citations=[c.copy() for c in citations],
            status=status,
            retrieval_trace={
                "has_conflicts": context_result.has_conflicts,
                "stale_sources": context_result.stale_sources,
                "query_type": analysis.query_type,
                "intent": analysis.intent,
                "rewritten_query": analysis.rewritten_query,
                "hallucination_action": hallucination_result.action,
                "unsupported_citations": citation_validation.unsupported_citations,
            },
        )
        db.add(result_record)
        await db.flush()

        # Save retrieval trace — skip chunks not in DB (e.g. stale Qdrant entries)
        used_chunk_ids = {str(c.chunk_id) for c in context_result.chunks_used}
        chunk_ids_to_check = [str(c.chunk_id) for c in ranked]
        existing_chunk_ids = await _get_existing_chunk_ids(db, chunk_ids_to_check)

        for rank, chunk in enumerate(ranked, start=1):
            if str(chunk.chunk_id) not in existing_chunk_ids:
                continue
            chunk_record = RetrievedChunkModel(
                query_result_id=result_record.id,
                chunk_id=chunk.chunk_id,
                retrieval_method=chunk.retrieval_method,
                vector_score=chunk.vector_score,
                bm25_score=chunk.bm25_score,
                freshness_score=chunk.freshness_score,
                rerank_score=chunk.rerank_score,
                final_score=chunk.final_score,
                rank_position=rank,
                was_used_in_context=str(chunk.chunk_id) in used_chunk_ids,
            )
            db.add(chunk_record)

        await db.flush()

        # Failed/weak answers become tracked knowledge gaps for admins to fill.
        if status == "low_confidence":
            gap_reason = "hallucination_blocked" if hallucination_result.action == "block" else "low_confidence"
            weak = [
                {"title": c.document_title, "score": round(c.final_score, 4)}
                for c in context_result.chunks_used[:3]
            ]
            try:
                await record_knowledge_gap(
                    db, workspace_id, query, gap_reason,
                    query_id=query_record.id, weak_sources=weak,
                )
            except Exception as e:
                logger.warning("knowledge_gap.record_failed", error=str(e))

        logger.info(
            "pipeline.complete",
            query_id=str(query_record.id),
            confidence=gen_result.confidence,
            faithfulness=hallucination_result.faithfulness_score,
            citation_accuracy=citation_validation.citation_accuracy,
            hallucination_action=hallucination_result.action,
            status=status,
            total_ms=timings["total_ms"],
            cost_usd=float(cost),
        )

        return {
            "query_id": query_record.id,
            "result_id": result_record.id,
            "session_id": query_record.session_id,
            "answer": answer,
            "citations": citations,
            "confidence_score": gen_result.confidence,
            "faithfulness_score": hallucination_result.faithfulness_score,
            "hallucination_score": hallucination_result.hallucination_score,
            "citation_accuracy": citation_validation.citation_accuracy,
            "status": status,
            "has_conflicts": context_result.has_conflicts,
            "follow_up_suggestions": gen_result.follow_up_suggestions,
            "escalation_needed": gen_result.escalation_needed,
            "escalation_reason": gen_result.escalation_reason,
            "latency_breakdown": timings,
            "token_usage": {
                "prompt_tokens": gen_result.prompt_tokens,
                "completion_tokens": gen_result.completion_tokens,
                "total_tokens": gen_result.total_tokens,
            },
            "cost_usd": float(cost),
            "retrieval_trace": {
                "has_conflicts": context_result.has_conflicts,
                "stale_sources": context_result.stale_sources,
                "query_type": analysis.query_type,
                "intent": analysis.intent,
                "rewritten_query": analysis.rewritten_query,
                "hallucination_action": hallucination_result.action,
                "unsupported_citations": citation_validation.unsupported_citations,
            },
        }

    except Exception as e:
        logger.error("pipeline.failed", query_id=str(query_record.id), error=str(e))
        timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)

        result_record = QueryResult(
            query_id=query_record.id,
            answer="I'm temporarily unable to process your question. Please try again.",
            confidence_score=0.0,
            latency_ms=timings.get("total_ms", 0),
            latency_breakdown=timings,
            status="error",
            error_message=str(e),
        )
        db.add(result_record)
        await db.flush()
        raise


async def _save_no_answer(
    db: AsyncSession,
    query_record: Query,
    timings: dict,
    total_start: float,
) -> dict:
    timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)
    answer = "I couldn't find relevant information for this question in the knowledge base."

    result_record = QueryResult(
        query_id=query_record.id,
        answer=answer,
        confidence_score=0.0,
        latency_ms=timings["total_ms"],
        latency_breakdown=timings,
        status="no_answer",
    )
    db.add(result_record)
    await db.flush()

    try:
        await record_knowledge_gap(
            db, query_record.workspace_id, query_record.original_query,
            "no_answer", query_id=query_record.id,
        )
    except Exception as e:
        logger.warning("knowledge_gap.record_failed", error=str(e))

    return {
        "query_id": query_record.id,
        "result_id": result_record.id,
        "session_id": query_record.session_id,
        "answer": answer,
        "citations": [],
        "confidence_score": 0.0,
        "status": "no_answer",
        "has_conflicts": False,
        "follow_up_suggestions": [],
        "escalation_needed": False,
        "escalation_reason": None,
        "latency_breakdown": timings,
        "token_usage": {},
        "cost_usd": 0.0,
    }


async def _timed(fn, *args):
    """Run a blocking fn in a worker thread; return (result, elapsed_ms)."""
    t0 = time.perf_counter()
    result = await asyncio.to_thread(fn, *args)
    return result, int((time.perf_counter() - t0) * 1000)


async def _save_verified_answer(
    db: AsyncSession,
    query_record: Query,
    va,
    score: float,
    timings: dict,
    total_start: float,
) -> dict:
    timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)
    trace = {"verified": True, "verified_answer_id": str(va.id), "match_score": round(score, 4)}

    result_record = QueryResult(
        query_id=query_record.id,
        answer=va.answer,
        confidence_score=1.0,
        latency_ms=timings["total_ms"],
        latency_breakdown=timings,
        cost_usd=0.0,
        status="success",
        retrieval_trace=trace,
    )
    db.add(result_record)
    await db.flush()

    return {
        "query_id": query_record.id,
        "result_id": result_record.id,
        "session_id": query_record.session_id,
        "answer": va.answer,
        "citations": [],
        "confidence_score": 1.0,
        "verified": True,
        "status": "success",
        "has_conflicts": False,
        "follow_up_suggestions": [],
        "escalation_needed": False,
        "escalation_reason": None,
        "latency_breakdown": timings,
        "token_usage": {},
        "cost_usd": 0.0,
        "retrieval_trace": trace,
    }


def _calculate_total_cost(
    query_tokens: int,
    reranked_count: int,
    gen_result: GenerationResult,
) -> float:
    embed_cost = calculate_embedding_cost(query_tokens)
    rerank_cost = calculate_rerank_cost(reranked_count)
    llm_cost = calculate_llm_cost(gen_result.prompt_tokens, gen_result.completion_tokens)
    return embed_cost + rerank_cost + llm_cost


def _build_citations(
    gen_result: GenerationResult,
    chunks_used: list[RetrievedChunk],
) -> list[dict]:
    citations = []
    for idx in gen_result.citations_used:
        if 1 <= idx <= len(chunks_used):
            chunk = chunks_used[idx - 1]
            citations.append({
                "index": idx,
                "document_title": chunk.document_title,
                "chunk_snippet": chunk.content[:200],
                "document_id": str(chunk.document_id),
                "relevance_score": chunk.final_score or chunk.rrf_score,
            })
    return citations


# Keywords that signal the user explicitly wants to restrict to a source type.
_SOURCE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pdf": ("pdf",),
    "markdown": ("markdown",),
    "text": ("text file", "plain text"),
    "html": ("html", "web page", "webpage"),
    "csv": ("csv", "spreadsheet", "ticket", "tickets"),
    "faq": ("faq", "frequently asked"),
    "slack_export": ("slack",),
    "release_note": ("release note", "release notes", "changelog"),
    "notion": ("notion",),
    "github": ("github", "repo", "repository", "issue", "pull request"),
    "web": ("website", "web page", "scraped", "crawl"),
}


async def _validate_filters(
    db: AsyncSession, workspace_id: uuid.UUID, metadata_filters: dict | None,
    query_text: str = "",
) -> dict | None:
    """Validate the source_type filter from query understanding.

    Two guards:
    1. Only honor the filter if the user actually referenced a source/type in
       the query. Query understanding tends to emit this filter spuriously
       (listing the common sample-data types), which silently excludes
       connector-sourced docs (notion/github/web) and tanks recall.
    2. Drop requested types that don't exist in the workspace.
    """
    if not metadata_filters or not metadata_filters.get("source_types"):
        return metadata_filters

    requested = metadata_filters["source_types"]
    q = (query_text or "").lower()
    referenced = any(
        kw in q for st in requested for kw in _SOURCE_TYPE_KEYWORDS.get(st, (st,))
    )
    if not referenced:
        logger.info("pipeline.source_filter_ignored", requested=requested)
        return {k: v for k, v in metadata_filters.items() if k != "source_types"}

    from sqlalchemy import text
    result = await db.execute(
        text("SELECT DISTINCT source_type FROM documents WHERE workspace_id = :wid AND status = 'active'"),
        {"wid": str(workspace_id)},
    )
    valid_types = {row[0] for row in result.fetchall()}

    matched = [st for st in requested if st in valid_types]

    if not matched:
        logger.info("pipeline.filters_dropped", requested=requested, valid=list(valid_types))
        return None

    return {**metadata_filters, "source_types": matched}


async def _get_existing_chunk_ids(db: AsyncSession, chunk_ids: list[str]) -> set[str]:
    """Check which chunk IDs actually exist in the database."""
    if not chunk_ids:
        return set()
    from sqlalchemy import text
    placeholders = ", ".join(f"'{cid}'::uuid" for cid in chunk_ids)
    sql = text(f"SELECT id FROM document_chunks WHERE id IN ({placeholders})")
    result = await db.execute(sql)
    return {str(row.id) for row in result.fetchall()}


# ---------------------------------------------------------------------------
# Streaming pipeline
# ---------------------------------------------------------------------------

def _citations_from_text(answer: str, chunks_used: list[RetrievedChunk]) -> list[dict]:
    """Build citation details from [N] markers in a plain-text answer."""
    indices = sorted({int(m) for m in re.findall(r"\[(\d+)\]", answer)})
    citations = []
    for idx in indices:
        if 1 <= idx <= len(chunks_used):
            chunk = chunks_used[idx - 1]
            citations.append({
                "index": idx,
                "document_title": chunk.document_title,
                "chunk_snippet": chunk.content[:200],
                "document_id": str(chunk.document_id),
                "relevance_score": chunk.final_score or chunk.rrf_score,
            })
    return citations


async def process_query_stream(
    query: str,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    session_id: uuid.UUID | None = None,
    workspace_name: str = "your organization",
):
    """Streaming variant of process_query.

    Yields event dicts: {"type":"token"|"verdict"|"done"|"error", "data": ...}.
    Safety checks ALWAYS run AFTER streaming — the answer is only "finalized" once
    verified. If the hallucination check blocks it, the verdict carries an
    `answer_override` so the frontend replaces the streamed text.
    """
    timings: dict[str, int] = {}
    total_start = time.perf_counter()

    query_record = Query(
        workspace_id=workspace_id,
        user_id=user_id,
        original_query=query,
        session_id=session_id or uuid.uuid4(),
    )
    db.add(query_record)
    await db.flush()

    try:
        # Stage 0: verified-answer shortcut
        match = await match_verified_answer(db, workspace_id, query)
        if match:
            va, score = match
            yield {"type": "token", "data": va.answer}
            timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)
            trace = {"verified": True, "verified_answer_id": str(va.id), "match_score": round(score, 4)}
            result_record = QueryResult(
                query_id=query_record.id, answer=va.answer, confidence_score=1.0,
                latency_ms=timings["total_ms"], latency_breakdown=timings, cost_usd=0.0,
                status="success", retrieval_trace=trace,
            )
            db.add(result_record)
            await db.flush()
            yield {"type": "verdict", "data": {
                "query_id": str(query_record.id), "result_id": str(result_record.id),
                "session_id": str(query_record.session_id), "status": "success",
                "confidence": 1.0, "verified": True, "citations": [],
                "has_conflicts": False, "follow_up_suggestions": [], "note": None,
                "answer_override": None,
            }}
            yield {"type": "done"}
            return

        # Stage 1: query understanding
        analysis = analyze_query(query)
        search_query = analysis.rewritten_query
        query_record.rewritten_query = search_query
        query_record.query_type = analysis.query_type
        query_record.intent = analysis.intent
        query_record.metadata_filters = analysis.metadata_filters
        retrieval_filters = await _validate_filters(
            db, workspace_id, analysis.metadata_filters, query_text=query
        )

        # Stage 2: retrieval (+ retry without filters)
        retrieved = await hybrid_retrieve(
            search_query, workspace_id, db, top_k=settings.RETRIEVAL_TOP_K,
            filters=retrieval_filters, date_sensitive=analysis.date_sensitive,
        )
        if not retrieved and retrieval_filters:
            retrieved = await hybrid_retrieve(
                search_query, workspace_id, db, top_k=settings.RETRIEVAL_TOP_K,
                date_sensitive=analysis.date_sensitive,
            )

        # Stage 3-4: rerank + context
        ranked = []
        context_result = None
        context_text = ""
        if retrieved:
            ranked = rerank(search_query, retrieved, top_k=settings.RERANK_TOP_K)
            context_result = build_context(ranked, token_budget=settings.CONTEXT_TOKEN_BUDGET)
            context_text = context_result.formatted_context

        if not context_text.strip():
            no_answer = "I couldn't find relevant information for this question in the knowledge base."
            yield {"type": "token", "data": no_answer}
            timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)
            result_record = QueryResult(
                query_id=query_record.id, answer=no_answer, confidence_score=0.0,
                latency_ms=timings["total_ms"], latency_breakdown=timings, status="no_answer",
            )
            db.add(result_record)
            await db.flush()
            try:
                await record_knowledge_gap(db, workspace_id, query, "no_answer", query_id=query_record.id)
            except Exception as e:
                logger.warning("knowledge_gap.record_failed", error=str(e))
            yield {"type": "verdict", "data": {
                "query_id": str(query_record.id), "result_id": str(result_record.id),
                "session_id": str(query_record.session_id), "status": "no_answer",
                "confidence": 0.0, "verified": False, "citations": [],
                "has_conflicts": False, "follow_up_suggestions": [], "note": None,
                "answer_override": None,
            }}
            yield {"type": "done"}
            return

        # Stage 5: stream generation (plain text)
        full_answer = ""
        gen_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        t0 = time.perf_counter()
        for event in generate_answer_stream(query, context_text, workspace_name):
            if event["type"] == "token":
                full_answer += event["data"]
                yield {"type": "token", "data": event["data"]}
            elif event["type"] == "usage":
                gen_usage = event["data"]
        timings["generation_ms"] = int((time.perf_counter() - t0) * 1000)

        # Stages 6 & 7: validation runs AFTER streaming, in parallel
        cited_indices = sorted({int(m) for m in re.findall(r"\[(\d+)\]", full_answer)})
        (citation_validation, _), (hallucination_result, _) = await asyncio.gather(
            _timed(validate_citations, full_answer, cited_indices, context_result.chunks_used),
            _timed(check_hallucination, full_answer, context_text),
        )

        # Confidence from faithfulness (more trustworthy than model self-report)
        faithfulness = hallucination_result.faithfulness_score
        confidence = faithfulness if faithfulness is not None else 0.5

        status = "success"
        note = None
        answer_override = None
        stored_answer = full_answer
        if hallucination_result.action == "block":
            status = "low_confidence"
            answer_override = (
                "I was unable to generate a fully reliable answer. "
                "Here are the most relevant sources I found:\n\n"
                + "\n".join(
                    f"- {c.document_title}: {c.content[:150]}..."
                    for c in context_result.chunks_used[:5]
                )
            )
            stored_answer = answer_override
        elif hallucination_result.action == "disclaimer":
            note = (
                "This answer could not be automatically verified against the sources. Please double-check important details."
                if hallucination_result.verification_failed
                else "Some statements in this answer may not be fully supported by the available sources."
            )
            stored_answer = full_answer + "\n\nNote: " + note
        elif confidence < 0.6:
            status = "low_confidence"

        if context_result.stale_sources:
            sources_str = ", ".join(context_result.stale_sources[:3])
            stale_note = f"Some information comes from potentially outdated sources ({sources_str}). Please verify with the latest documentation."
            note = (note + " " + stale_note) if note else stale_note
            stored_answer += f"\n\nNote: {stale_note}"

        citations = _citations_from_text(full_answer, context_result.chunks_used)

        timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)
        query_tokens = count_tokens(query)
        validation_cost = calculate_llm_cost(
            citation_validation.prompt_tokens + hallucination_result.prompt_tokens,
            citation_validation.completion_tokens + hallucination_result.completion_tokens,
            model="gpt-4o-mini",
        )
        qu_cost = calculate_llm_cost(analysis.prompt_tokens, analysis.completion_tokens, model="gpt-4o-mini")
        gen_cost = calculate_llm_cost(gen_usage.get("prompt_tokens", 0), gen_usage.get("completion_tokens", 0))
        cost = calculate_embedding_cost(query_tokens) + calculate_rerank_cost(len(retrieved)) + gen_cost + validation_cost + qu_cost

        result_record = QueryResult(
            query_id=query_record.id, answer=stored_answer, confidence_score=confidence,
            faithfulness_score=hallucination_result.faithfulness_score,
            hallucination_score=hallucination_result.hallucination_score,
            citation_accuracy=citation_validation.citation_accuracy,
            latency_ms=timings["total_ms"], latency_breakdown=timings,
            token_usage=gen_usage, cost_usd=cost,
            citations=[c.copy() for c in citations], status=status,
            retrieval_trace={
                "has_conflicts": context_result.has_conflicts,
                "stale_sources": context_result.stale_sources,
                "query_type": analysis.query_type, "intent": analysis.intent,
                "rewritten_query": analysis.rewritten_query,
                "hallucination_action": hallucination_result.action, "streamed": True,
            },
        )
        db.add(result_record)
        await db.flush()

        used_chunk_ids = {str(c.chunk_id) for c in context_result.chunks_used}
        existing = await _get_existing_chunk_ids(db, [str(c.chunk_id) for c in ranked])
        for rank, chunk in enumerate(ranked, start=1):
            if str(chunk.chunk_id) not in existing:
                continue
            db.add(RetrievedChunkModel(
                query_result_id=result_record.id, chunk_id=chunk.chunk_id,
                retrieval_method=chunk.retrieval_method, vector_score=chunk.vector_score,
                bm25_score=chunk.bm25_score, freshness_score=chunk.freshness_score,
                rerank_score=chunk.rerank_score, final_score=chunk.final_score,
                rank_position=rank, was_used_in_context=str(chunk.chunk_id) in used_chunk_ids,
            ))
        await db.flush()

        if status == "low_confidence":
            gap_reason = "hallucination_blocked" if hallucination_result.action == "block" else "low_confidence"
            weak = [
                {"title": c.document_title, "score": round(c.final_score, 4)}
                for c in context_result.chunks_used[:3]
            ]
            try:
                await record_knowledge_gap(db, workspace_id, query, gap_reason, query_id=query_record.id, weak_sources=weak)
            except Exception as e:
                logger.warning("knowledge_gap.record_failed", error=str(e))

        yield {"type": "verdict", "data": {
            "query_id": str(query_record.id), "result_id": str(result_record.id),
            "session_id": str(query_record.session_id), "status": status,
            "confidence": confidence, "verified": False, "citations": citations,
            "has_conflicts": context_result.has_conflicts, "follow_up_suggestions": [],
            "note": note, "answer_override": answer_override,
        }}
        yield {"type": "done"}

    except Exception as e:
        logger.error("pipeline_stream.failed", query_id=str(query_record.id), error=str(e))
        yield {"type": "error", "data": "I'm temporarily unable to process your question. Please try again."}
