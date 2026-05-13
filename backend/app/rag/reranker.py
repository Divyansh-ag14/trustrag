import structlog
import cohere

from app.config import settings
from app.rag.retriever import RetrievedChunk

logger = structlog.get_logger()

_client: cohere.Client | None = None


def _get_client() -> cohere.Client:
    global _client
    if _client is None:
        _client = cohere.Client(api_key=settings.COHERE_API_KEY)
    return _client


def _normalize(values: list[float]) -> list[float]:
    if not values:
        return values
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [0.5] * len(values)
    return [(v - min_v) / (max_v - min_v) for v in values]


def rerank(
    query: str,
    chunks: list[RetrievedChunk],
    top_k: int = 10,
    weights: dict | None = None,
) -> list[RetrievedChunk]:
    if not chunks:
        return []

    w = weights or {
        "vector": 0.35,
        "bm25": 0.15,
        "rerank": 0.40,
        "freshness": 0.10,
    }

    try:
        client = _get_client()
        docs = [c.content for c in chunks]

        response = client.rerank(
            model=settings.RERANK_MODEL,
            query=query,
            documents=docs,
            top_n=len(chunks),
        )

        rerank_scores = {r.index: r.relevance_score for r in response.results}

        for i, chunk in enumerate(chunks):
            chunk.rerank_score = rerank_scores.get(i, 0.0)

        logger.info("reranker.cohere_complete", input_count=len(chunks))

    except Exception as e:
        logger.warning("reranker.cohere_failed, using rrf scores only", error=str(e))
        for chunk in chunks:
            chunk.rerank_score = chunk.rrf_score
        ranked = sorted(chunks, key=lambda c: c.rrf_score, reverse=True)
        return ranked[:top_k]

    vector_scores = _normalize([c.vector_score for c in chunks])
    bm25_scores = _normalize([c.bm25_score for c in chunks])
    rerank_scores_list = [c.rerank_score for c in chunks]
    freshness_scores = [c.freshness_score for c in chunks]

    for i, chunk in enumerate(chunks):
        chunk.final_score = (
            w["vector"] * vector_scores[i]
            + w["bm25"] * bm25_scores[i]
            + w["rerank"] * rerank_scores_list[i]
            + w["freshness"] * freshness_scores[i]
        )

    ranked = sorted(chunks, key=lambda c: c.final_score, reverse=True)

    logger.info(
        "reranker.complete",
        input_count=len(chunks),
        output_count=min(top_k, len(ranked)),
        top_score=ranked[0].final_score if ranked else 0,
    )

    return ranked[:top_k]
