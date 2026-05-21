from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.rag.retriever import RetrievedChunk
from app.utils.tokens import count_tokens

logger = structlog.get_logger()

STALENESS_THRESHOLD_DAYS = 180


@dataclass
class ContextResult:
    formatted_context: str
    chunks_used: list[RetrievedChunk]
    total_tokens: int
    has_conflicts: bool = False
    stale_sources: list[str] = field(default_factory=list)


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    tokens_a = set(text_a.lower().split())
    tokens_b = set(text_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _deduplicate(chunks: list[RetrievedChunk], threshold: float = 0.8) -> list[RetrievedChunk]:
    if not chunks:
        return chunks

    unique: list[RetrievedChunk] = [chunks[0]]
    for chunk in chunks[1:]:
        is_dup = False
        for existing in unique:
            if _jaccard_similarity(chunk.content, existing.content) > threshold:
                is_dup = True
                break
        if not is_dup:
            unique.append(chunk)

    return unique


def _enforce_diversity(
    chunks: list[RetrievedChunk],
    max_per_doc: int = 3,
) -> list[RetrievedChunk]:
    doc_counts: dict[str, int] = {}
    diverse: list[RetrievedChunk] = []

    for chunk in chunks:
        doc_key = str(chunk.document_id)
        current = doc_counts.get(doc_key, 0)
        if current < max_per_doc:
            diverse.append(chunk)
            doc_counts[doc_key] = current + 1

    return diverse


def _detect_stale_sources(chunks: list[RetrievedChunk]) -> list[str]:
    """Flag sources older than STALENESS_THRESHOLD_DAYS."""
    now = datetime.now(timezone.utc)
    stale = []
    for chunk in chunks:
        if chunk.doc_updated_at:
            age_days = (now - chunk.doc_updated_at).days
            if age_days > STALENESS_THRESHOLD_DAYS:
                title = chunk.document_title
                if title not in stale:
                    stale.append(title)
    return stale


def _detect_conflicts(chunks: list[RetrievedChunk]) -> bool:
    """Check if top chunks from different documents might conflict.

    Heuristic: if chunks from 2+ documents on similar topics have update dates
    more than 90 days apart, flag potential conflict for the generator to handle.
    """
    if len(chunks) < 2:
        return False

    doc_dates: dict[str, datetime] = {}
    for chunk in chunks:
        doc_key = str(chunk.document_id)
        if chunk.doc_updated_at and doc_key not in doc_dates:
            doc_dates[doc_key] = chunk.doc_updated_at

    if len(doc_dates) < 2:
        return False

    dates = list(doc_dates.values())
    for i in range(len(dates)):
        for j in range(i + 1, len(dates)):
            gap_days = abs((dates[i] - dates[j]).days)
            if gap_days > 90:
                return True

    return False


def _format_citation(index: int, chunk: RetrievedChunk) -> str:
    date_str = ""
    if chunk.doc_updated_at:
        date_str = f", updated {chunk.doc_updated_at.strftime('%Y-%m-%d')}"

    return (
        f"[{index}] (Source: {chunk.document_title}{date_str})\n"
        f"{chunk.content}"
    )


def build_context(
    ranked_chunks: list[RetrievedChunk],
    token_budget: int = 4000,
    max_per_doc: int = 3,
) -> ContextResult:
    if not ranked_chunks:
        return ContextResult(
            formatted_context="",
            chunks_used=[],
            total_tokens=0,
        )

    deduped = _deduplicate(ranked_chunks)
    diverse = _enforce_diversity(deduped, max_per_doc)

    selected: list[RetrievedChunk] = []
    total_tokens = 0

    for chunk in diverse:
        chunk_tokens = count_tokens(chunk.content)
        header_tokens = count_tokens(f"[{len(selected) + 1}] (Source: {chunk.document_title})\n")
        needed = chunk_tokens + header_tokens

        if total_tokens + needed > token_budget:
            if not selected:
                selected.append(chunk)
                total_tokens += needed
            break

        selected.append(chunk)
        total_tokens += needed

    has_conflicts = _detect_conflicts(selected)
    stale_sources = _detect_stale_sources(selected)

    context_parts = []
    for i, chunk in enumerate(selected, start=1):
        context_parts.append(_format_citation(i, chunk))

    if has_conflicts:
        context_parts.insert(0, "NOTE: The following sources may contain conflicting information from different time periods. Present all perspectives with their dates.")

    formatted = "\n\n".join(context_parts)

    logger.info(
        "context_builder.complete",
        input_chunks=len(ranked_chunks),
        after_dedup=len(deduped),
        after_diversity=len(diverse),
        selected=len(selected),
        total_tokens=total_tokens,
        has_conflicts=has_conflicts,
        stale_sources=stale_sources,
    )

    return ContextResult(
        formatted_context=formatted,
        chunks_used=selected,
        total_tokens=total_tokens,
        has_conflicts=has_conflicts,
        stale_sources=stale_sources,
    )
