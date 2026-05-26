import os
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.config import settings
from app.database import get_db, get_qdrant
from app.ingestion.processor import _collection_name
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.schemas.document import ChunkListResponse, ChunkResponse, DocumentListResponse, DocumentResponse
from app.utils.file_validation import validate_file_content, validate_filename
from app.workers.ingestion_tasks import process_document_task

router = APIRouter(prefix="/documents", tags=["documents"])
logger = structlog.get_logger()

ALLOWED_EXTENSIONS = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".txt": "text",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
}


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "member")),
):
    ext = Path(file.filename).suffix.lower()
    source_type = ALLOWED_EXTENSIONS.get(ext)
    if not source_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {list(ALLOWED_EXTENSIONS.keys())}",
        )

    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    content = await file.read()

    # Validate magic bytes
    if not validate_file_content(content, source_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content does not match expected type: {source_type}",
        )

    safe_name = validate_filename(file.filename)
    upload_dir = Path(settings.UPLOAD_DIR) / str(user.workspace_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4()
    file_path = upload_dir / f"{file_id}{ext}"

    with open(file_path, "wb") as f:
        f.write(content)

    doc_title = title or Path(file.filename).stem
    doc = Document(
        workspace_id=user.workspace_id,
        title=doc_title,
        source_type=source_type,
        status="processing",
        uploaded_by=user.id,
    )
    db.add(doc)
    await db.flush()

    job = IngestionJob(
        workspace_id=user.workspace_id,
        document_id=doc.id,
        status="queued",
    )
    db.add(job)
    await db.flush()

    process_document_task.delay(str(doc.id), str(file_path))

    logger.info("document.uploaded", document_id=str(doc.id), source_type=source_type)
    return doc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status_filter: str | None = None,
    source_type: str | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Document).where(Document.workspace_id == user.workspace_id)
    count_query = select(func.count(Document.id)).where(Document.workspace_id == user.workspace_id)

    if status_filter:
        query = query.where(Document.status == status_filter)
        count_query = count_query.where(Document.status == status_filter)
    if source_type:
        query = query.where(Document.source_type == source_type)
        count_query = count_query.where(Document.source_type == source_type)

    query = query.order_by(Document.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    docs = result.scalars().all()
    total = (await db.execute(count_query)).scalar()

    return DocumentListResponse(documents=[DocumentResponse.model_validate(d) for d in docs], total=total)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == user.workspace_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == user.workspace_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        qdrant = get_qdrant()
        collection = _collection_name(user.workspace_id)
        chunk_result = await db.execute(
            select(DocumentChunk.embedding_id).where(DocumentChunk.document_id == document_id)
        )
        embedding_ids = [r for r in chunk_result.scalars().all() if r]
        if embedding_ids:
            qdrant.delete(collection_name=collection, points_selector=embedding_ids)
    except Exception as e:
        logger.warning("document.delete.qdrant_cleanup_failed", error=str(e))

    doc.status = "archived"
    await db.flush()


@router.post("/{document_id}/reindex", response_model=DocumentResponse)
async def reindex_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == user.workspace_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    upload_dir = Path(settings.UPLOAD_DIR) / str(user.workspace_id)
    files = list(upload_dir.glob(f"*"))
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Original file not found")

    doc.status = "processing"
    doc.version += 1

    job = IngestionJob(workspace_id=user.workspace_id, document_id=doc.id, status="queued")
    db.add(job)
    await db.flush()

    process_document_task.delay(str(doc.id), str(files[0]))
    return doc


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(
    document_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id, Document.workspace_id == user.workspace_id)
    )
    if not doc_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    query = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    chunks = result.scalars().all()

    count = (
        await db.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id))
    ).scalar()

    return ChunkListResponse(
        chunks=[ChunkResponse.model_validate(c) for c in chunks],
        total=count,
    )
