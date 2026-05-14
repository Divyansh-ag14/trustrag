import time
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.query import Query, QueryResult, RetrievedChunk as RetrievedChunkModel
from app.rag.context_builder import build_context
from app.rag.generator import generate, GenerationResult
from app.rag.reranker import rerank
from app.rag.retriever import hybrid_retrieve, RetrievedChunk
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
        t0 = time.perf_counter()
        retrieved = await hybrid_retrieve(query, workspace_id, db, top_k=settings.RETRIEVAL_TOP_K)
        timings["retrieval_ms"] = int((time.perf_counter() - t0) * 1000)

        if not retrieved:
            return await _save_no_answer(db, query_record, timings, total_start)

        t0 = time.perf_counter()
        ranked = rerank(query, retrieved, top_k=settings.RERANK_TOP_K)
        timings["rerank_ms"] = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        context_result = build_context(ranked, token_budget=settings.CONTEXT_TOKEN_BUDGET)
        timings["context_build_ms"] = int((time.perf_counter() - t0) * 1000)

        if not context_result.formatted_context.strip():
            return await _save_no_answer(db, query_record, timings, total_start)

        t0 = time.perf_counter()
        gen_result = generate(query, context_result.formatted_context, workspace_name)
        timings["generation_ms"] = int((time.perf_counter() - t0) * 1000)

        timings["total_ms"] = int((time.perf_counter() - total_start) * 1000)

        query_tokens = count_tokens(query)
        cost = _calculate_total_cost(query_tokens, len(retrieved), gen_result)

        citations = _build_citations(gen_result, context_result.chunks_used)

        status = "success"
        if gen_result.confidence < 0.6:
            status = "low_confidence"

        result_record = QueryResult(
            query_id=query_record.id,
            answer=gen_result.answer,
            confidence_score=gen_result.confidence,
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
            has_conflicts=gen_result.has_conflicts,
        )
        db.add(result_record)
        await db.flush()

        used_chunk_ids = {str(c.chunk_id) for c in context_result.chunks_used}
        for rank, chunk in enumerate(ranked, start=1):
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

        logger.info(
            "pipeline.complete",
            query_id=str(query_record.id),
            confidence=gen_result.confidence,
            status=status,
            total_ms=timings["total_ms"],
            cost_usd=float(cost),
        )

        return {
            "query_id": query_record.id,
            "result_id": result_record.id,
            "session_id": query_record.session_id,
            "answer": gen_result.answer,
            "citations": citations,
            "confidence_score": gen_result.confidence,
            "status": status,
            "has_conflicts": gen_result.has_conflicts,
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
