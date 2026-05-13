from dataclasses import dataclass

import structlog

from app.rag.retriever import RetrievedChunk
from app.utils.tokens import count_tokens

logger = structlog.get_logger()


@dataclass
class ContextResult:
    formatted_context: str
    chunks_used: list[RetrievedChunk]
    total_tokens: int
    has_conflicts: bool = False


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

    context_parts = []
    for i, chunk in enumerate(selected, start=1):
        context_parts.append(_format_citation(i, chunk))

    formatted = "\n\n".join(context_parts)

    logger.info(
        "context_builder.complete",
        input_chunks=len(ranked_chunks),
        after_dedup=len(deduped),
        after_diversity=len(diverse),
        selected=len(selected),
        total_tokens=total_tokens,
    )

    return ContextResult(
        formatted_context=formatted,
        chunks_used=selected,
        total_tokens=total_tokens,
    )
