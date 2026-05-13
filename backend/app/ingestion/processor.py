import hashlib
import uuid
from datetime import datetime, timezone

import structlog
from qdrant_client.models import PointStruct, VectorParams, Distance
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_qdrant
from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import embed_texts
from app.ingestion.parsers import PARSERS
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob

logger = structlog.get_logger()

COLLECTION_PREFIX = "workspace_"


def _collection_name(workspace_id: uuid.UUID) -> str:
    return f"{COLLECTION_PREFIX}{str(workspace_id).replace('-', '_')}"


def ensure_collection(workspace_id: uuid.UUID) -> None:
    qdrant = get_qdrant()
    name = _collection_name(workspace_id)
    collections = [c.name for c in qdrant.get_collections().collections]
    if name not in collections:
        qdrant.create_collection(
            collection_name=name,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )
        logger.info("qdrant.collection_created", collection=name)


async def process_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    file_path: str,
) -> None:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one()

    job_result = await db.execute(
        select(IngestionJob).where(IngestionJob.document_id == document_id).order_by(IngestionJob.created_at.desc())
    )
    job = job_result.scalar_one_or_none()

    try:
        if job:
            job.status = "processing"
            job.started_at = datetime.now(timezone.utc)
            await db.flush()

        parser_cls = PARSERS.get(doc.source_type)
        if not parser_cls:
            raise ValueError(f"No parser for source type: {doc.source_type}")

        logger.info("ingestion.parsing", document_id=str(document_id), source_type=doc.source_type)
        raw_text = parser_cls.parse(file_path)

        content_hash = hashlib.sha256(raw_text.encode()).hexdigest()
        doc.content_hash = content_hash

        logger.info("ingestion.chunking", document_id=str(document_id))
        chunks = chunk_text(raw_text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP, doc.title)

        logger.info("ingestion.embedding", document_id=str(document_id), chunk_count=len(chunks))
        texts = [c.content for c in chunks]
        embeddings = await embed_texts(texts)

        ensure_collection(doc.workspace_id)
        qdrant = get_qdrant()
        collection = _collection_name(doc.workspace_id)

        points = []
        db_chunks = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": str(document_id),
                    "workspace_id": str(doc.workspace_id),
                    "source_type": doc.source_type,
                    "document_title": doc.title,
                    "content_preview": chunk.content[:200],
                    "chunk_index": chunk.chunk_index,
                },
            ))

            db_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                embedding_id=point_id,
                metadata_=chunk.metadata,
            )
            db_chunks.append(db_chunk)

        batch_size = 100
        for i in range(0, len(points), batch_size):
            qdrant.upsert(collection_name=collection, points=points[i : i + batch_size])

        for db_chunk in db_chunks:
            db.add(db_chunk)

        doc.status = "active"
        doc.total_chunks = len(chunks)

        if job:
            job.status = "completed"
            job.chunks_created = len(chunks)
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 1.0

        await db.flush()
        logger.info(
            "ingestion.complete",
            document_id=str(document_id),
            chunks=len(chunks),
        )

    except Exception as e:
        logger.error("ingestion.failed", document_id=str(document_id), error=str(e))
        doc.status = "failed"
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
        await db.flush()
        raise
