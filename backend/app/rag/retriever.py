import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_qdrant
from app.ingestion.embedder import embed_single
from app.ingestion.processor import _collection_name

logger = structlog.get_logger()


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    content: str
    source_type: str
    chunk_index: int
    vector_score: float = 0.0
    bm25_score: float = 0.0
    rrf_score: float = 0.0
    freshness_score: float = 1.0
    doc_updated_at: datetime | None = None
    rerank_score: float = 0.0
    final_score: float = 0.0
    retrieval_method: str = "hybrid"


RRF_K = 60


def _rrf_score(rank: int) -> float:
    return 1.0 / (RRF_K + rank)


async def _vector_search(
    query: str,
    workspace_id: uuid.UUID,
    top_k: int,
    filters: dict | None = None,
) -> list[RetrievedChunk]:
    query_embedding = embed_single(query)
    qdrant = get_qdrant()
    collection = _collection_name(workspace_id)

    qdrant_filter = None
    if filters and filters.get("source_types"):
        qdrant_filter = Filter(
            must=[
                FieldCondition(key="source_type", match=MatchValue(value=st))
                for st in filters["source_types"]
            ]
        )

    results = qdrant.query_points(
        collection_name=collection,
        query=query_embedding,
        limit=top_k,
        query_filter=qdrant_filter,
        with_payload=True,
    )

    chunks = []
    for hit in results.points:
        payload = hit.payload or {}
        chunks.append(RetrievedChunk(
            chunk_id=uuid.UUID(payload.get("chunk_id", str(uuid.uuid4()))),
            document_id=uuid.UUID(payload.get("document_id", str(uuid.uuid4()))),
            document_title=payload.get("document_title", ""),
            content=payload.get("content_preview", ""),
            source_type=payload.get("source_type", ""),
            chunk_index=payload.get("chunk_index", 0),
            vector_score=hit.score,
            retrieval_method="vector",
        ))

    return chunks


async def _bm25_search(
    query: str,
    workspace_id: uuid.UUID,
    top_k: int,
    db: AsyncSession,
    filters: dict | None = None,
) -> list[RetrievedChunk]:
    filter_clause = ""
    params = {"workspace_id": str(workspace_id), "query": query, "limit": top_k}

    if filters and filters.get("source_types"):
        placeholders = ", ".join(f":st_{i}" for i in range(len(filters["source_types"])))
        filter_clause = f"AND d.source_type IN ({placeholders})"
        for i, st in enumerate(filters["source_types"]):
            params[f"st_{i}"] = st

    sql = text(f"""
        SELECT
            dc.id as chunk_id,
            dc.document_id,
            dc.content,
            dc.chunk_index,
            d.title as document_title,
            d.source_type,
            d.updated_at as doc_updated_at,
            ts_rank_cd(dc.search_vector, plainto_tsquery('english', :query)) as rank_score
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE d.workspace_id = CAST(:workspace_id AS uuid)
          AND d.status = 'active'
          AND dc.search_vector @@ plainto_tsquery('english', :query)
          {filter_clause}
        ORDER BY rank_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    chunks = []
    for row in rows:
        chunks.append(RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_title=row.document_title,
            content=row.content,
            source_type=row.source_type,
            chunk_index=row.chunk_index,
            bm25_score=float(row.rank_score),
            doc_updated_at=row.doc_updated_at,
            retrieval_method="bm25",
        ))

    return chunks


def _calculate_freshness(doc_updated_at: datetime | None) -> float:
    if not doc_updated_at:
        return 0.5
    days_since = (datetime.now(timezone.utc) - doc_updated_at).days
    return max(0.5, 1.0 - (days_since / 365))


def _fuse_results(
    vector_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    chunk_map: dict[str, RetrievedChunk] = {}

    for rank, chunk in enumerate(vector_results, start=1):
        key = str(chunk.chunk_id)
        if key not in chunk_map:
            chunk_map[key] = chunk
        chunk_map[key].vector_score = chunk.vector_score
        chunk_map[key].rrf_score += _rrf_score(rank)

    for rank, chunk in enumerate(bm25_results, start=1):
        key = str(chunk.chunk_id)
        if key not in chunk_map:
            chunk_map[key] = chunk
        chunk_map[key].bm25_score = chunk.bm25_score
        chunk_map[key].rrf_score += _rrf_score(rank)
        if chunk.doc_updated_at:
            chunk_map[key].doc_updated_at = chunk.doc_updated_at

    for chunk in chunk_map.values():
        chunk.freshness_score = _calculate_freshness(chunk.doc_updated_at)
        chunk.retrieval_method = "hybrid"

    fused = sorted(chunk_map.values(), key=lambda c: c.rrf_score, reverse=True)
    return fused[:top_k]


async def _load_full_content(
    chunks: list[RetrievedChunk],
    db: AsyncSession,
) -> list[RetrievedChunk]:
    if not chunks:
        return chunks

    chunk_ids = [str(c.chunk_id) for c in chunks]
    placeholders = ", ".join(f"'{cid}'::uuid" for cid in chunk_ids)

    sql = text(f"""
        SELECT id, content FROM document_chunks
        WHERE id IN ({placeholders})
    """)
    result = await db.execute(sql)
    content_map = {str(row.id): row.content for row in result.fetchall()}

    for chunk in chunks:
        full_content = content_map.get(str(chunk.chunk_id))
        if full_content:
            chunk.content = full_content

    return chunks


async def hybrid_retrieve(
    query: str,
    workspace_id: uuid.UUID,
    db: AsyncSession,
    top_k: int = 50,
    filters: dict | None = None,
) -> list[RetrievedChunk]:
    logger.info("retriever.start", query=query[:100], top_k=top_k)

    try:
        vector_results = await _vector_search(query, workspace_id, top_k, filters)
    except Exception as e:
        logger.warning("retriever.vector_search_failed", error=str(e))
        vector_results = []

    bm25_results = await _bm25_search(query, workspace_id, top_k, db, filters)

    if not vector_results and not bm25_results:
        logger.info("retriever.no_results")
        return []

    if not vector_results:
        fused = bm25_results[:top_k]
        for chunk in fused:
            chunk.rrf_score = chunk.bm25_score
    elif not bm25_results:
        fused = vector_results[:top_k]
        for chunk in fused:
            chunk.rrf_score = chunk.vector_score
    else:
        fused = _fuse_results(vector_results, bm25_results, top_k)

    fused = await _load_full_content(fused, db)

    logger.info(
        "retriever.complete",
        vector_count=len(vector_results),
        bm25_count=len(bm25_results),
        fused_count=len(fused),
    )

    return fused
