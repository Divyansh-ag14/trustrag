"""Evaluation runner — processes a golden dataset through the RAG pipeline and scores results."""

import time
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.evaluation.metrics import (
    average_precision,
    hit_rate,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.models.document import Document
from app.models.evaluation import EvaluationDataset, EvaluationItem, EvaluationRun
from app.rag.context_builder import build_context
from app.rag.generator import generate
from app.rag.reranker import rerank
from app.rag.retriever import hybrid_retrieve

logger = structlog.get_logger()

K = 10  # default top-k for retrieval metrics


async def _resolve_doc_titles_to_ids(
    db: AsyncSession, workspace_id: uuid.UUID, source_paths: list[str]
) -> list[str]:
    """Map expected source doc paths (e.g. 'policies/refund-policy.md') to document IDs.

    Matches by checking if the document title or source_url contains the path fragment.
    """
    if not source_paths:
        return []

    result = await db.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.status == "active",
        )
    )
    docs = result.scalars().all()

    matched_ids = []
    for path in source_paths:
        # Strip directory prefix if present, match on filename stem
        path_stem = path.rsplit("/", 1)[-1].replace(".md", "").replace("-", " ").lower()
        for doc in docs:
            title_lower = doc.title.lower()
            source_lower = (doc.source_url or "").lower()
            if path_stem in title_lower or path in source_lower:
                matched_ids.append(str(doc.id))
                break

    return matched_ids


async def run_evaluation(
    db: AsyncSession,
    run_id: uuid.UUID,
    dataset_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> dict:
    """Execute an evaluation run: process each item through the pipeline and compute metrics."""

    run = await db.get(EvaluationRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    run.status = "running"
    await db.flush()

    result = await db.execute(
        select(EvaluationItem).where(EvaluationItem.dataset_id == dataset_id)
    )
    items = result.scalars().all()

    if not items:
        run.status = "failed"
        run.error_message = "Dataset has no evaluation items"
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return {"error": "empty dataset"}

    per_item_results = []
    aggregate_metrics = {
        "recall_at_10": [],
        "precision_at_10": [],
        "mrr": [],
        "ndcg_at_10": [],
        "hit_rate": [],
        "avg_precision": [],
        "avg_latency_ms": [],
        "avg_confidence": [],
        "total_cost_usd": 0.0,
    }

    logger.info(
        "evaluation.start",
        run_id=str(run_id),
        dataset_id=str(dataset_id),
        item_count=len(items),
    )

    for idx, item in enumerate(items):
        try:
            item_result = await _evaluate_single_item(
                db, item, workspace_id, aggregate_metrics
            )
            per_item_results.append(item_result)
            logger.info(
                "evaluation.item_complete",
                item_index=idx + 1,
                question=item.question[:60],
                recall=item_result.get("recall_at_10", 0),
                confidence=item_result.get("confidence", 0),
            )
        except Exception as e:
            logger.error(
                "evaluation.item_failed",
                item_index=idx + 1,
                question=item.question[:60],
                error=str(e),
            )
            per_item_results.append({
                "item_id": str(item.id),
                "question": item.question,
                "status": "error",
                "error": str(e),
            })

    # Compute aggregate metrics
    final_metrics = {}
    for key in ["recall_at_10", "precision_at_10", "mrr", "ndcg_at_10", "hit_rate", "avg_precision"]:
        values = aggregate_metrics[key]
        final_metrics[key] = round(sum(values) / len(values), 4) if values else 0.0

    latencies = aggregate_metrics["avg_latency_ms"]
    final_metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies)) if latencies else 0
    confidences = aggregate_metrics["avg_confidence"]
    final_metrics["avg_confidence"] = round(sum(confidences) / len(confidences), 4) if confidences else 0.0
    final_metrics["total_cost_usd"] = round(aggregate_metrics["total_cost_usd"], 6)
    final_metrics["items_evaluated"] = len(per_item_results)
    final_metrics["items_passed"] = sum(
        1 for r in per_item_results if r.get("status") == "success"
    )

    run.metrics = final_metrics
    run.per_item_results = per_item_results
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    await db.flush()

    logger.info(
        "evaluation.complete",
        run_id=str(run_id),
        recall=final_metrics["recall_at_10"],
        mrr=final_metrics["mrr"],
        avg_latency=final_metrics["avg_latency_ms"],
    )

    return final_metrics


async def _evaluate_single_item(
    db: AsyncSession,
    item: EvaluationItem,
    workspace_id: uuid.UUID,
    aggregate_metrics: dict,
) -> dict:
    """Run a single evaluation item through the pipeline and compute its metrics."""
    start = time.perf_counter()

    # Resolve expected source doc paths to document IDs
    expected_doc_ids = await _resolve_doc_titles_to_ids(
        db, workspace_id, item.expected_source_docs
    )

    # Step 1: Retrieve
    retrieved = await hybrid_retrieve(
        item.question, workspace_id, db, top_k=settings.RETRIEVAL_TOP_K
    )

    # Get retrieved document IDs (deduplicated, preserving order)
    seen = set()
    retrieved_doc_ids = []
    for chunk in retrieved:
        doc_id = str(chunk.document_id)
        if doc_id not in seen:
            seen.add(doc_id)
            retrieved_doc_ids.append(doc_id)

    # Step 2: Rerank
    ranked = rerank(item.question, retrieved, top_k=settings.RERANK_TOP_K)

    # Get reranked document IDs
    seen_ranked = set()
    reranked_doc_ids = []
    for chunk in ranked:
        doc_id = str(chunk.document_id)
        if doc_id not in seen_ranked:
            seen_ranked.add(doc_id)
            reranked_doc_ids.append(doc_id)

    # Step 3: Build context and generate
    context_result = build_context(ranked, token_budget=settings.CONTEXT_TOKEN_BUDGET)

    answer_text = ""
    confidence = 0.0
    citations_used = []
    gen_cost = 0.0

    if context_result.formatted_context.strip():
        gen_result = generate(item.question, context_result.formatted_context, "AcmeSaaS")
        answer_text = gen_result.answer
        confidence = gen_result.confidence
        citations_used = gen_result.citations_used

        from app.utils.costs import calculate_llm_cost
        gen_cost = calculate_llm_cost(gen_result.prompt_tokens, gen_result.completion_tokens)

    latency_ms = int((time.perf_counter() - start) * 1000)

    # Compute retrieval metrics
    item_recall = recall_at_k(reranked_doc_ids, expected_doc_ids, K)
    item_precision = precision_at_k(reranked_doc_ids, expected_doc_ids, K)
    item_mrr = mrr(reranked_doc_ids, expected_doc_ids)
    item_ndcg = ndcg_at_k(reranked_doc_ids, expected_doc_ids, K)
    item_hit = hit_rate(reranked_doc_ids, expected_doc_ids, K)
    item_ap = average_precision(reranked_doc_ids, expected_doc_ids)

    # Accumulate
    aggregate_metrics["recall_at_10"].append(item_recall)
    aggregate_metrics["precision_at_10"].append(item_precision)
    aggregate_metrics["mrr"].append(item_mrr)
    aggregate_metrics["ndcg_at_10"].append(item_ndcg)
    aggregate_metrics["hit_rate"].append(item_hit)
    aggregate_metrics["avg_precision"].append(item_ap)
    aggregate_metrics["avg_latency_ms"].append(latency_ms)
    aggregate_metrics["avg_confidence"].append(confidence)
    aggregate_metrics["total_cost_usd"] += gen_cost

    has_citation = len(citations_used) > 0

    return {
        "item_id": str(item.id),
        "question": item.question,
        "expected_answer": item.expected_answer,
        "actual_answer": answer_text,
        "expected_source_docs": item.expected_source_docs,
        "retrieved_doc_ids": reranked_doc_ids[:5],
        "query_type": item.query_type,
        "difficulty": item.difficulty,
        "status": "success",
        "metrics": {
            "recall_at_10": round(item_recall, 4),
            "precision_at_10": round(item_precision, 4),
            "mrr": round(item_mrr, 4),
            "ndcg_at_10": round(item_ndcg, 4),
            "hit_rate": round(item_hit, 4),
            "avg_precision": round(item_ap, 4),
        },
        "confidence": confidence,
        "has_citation": has_citation,
        "latency_ms": latency_ms,
        "cost_usd": round(gen_cost, 6),
    }
