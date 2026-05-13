import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    source_type: str
    source_url: str | None = None
    version: int
    status: str
    metadata_: dict = Field(default_factory=dict, alias="metadata_")
    uploaded_by: uuid.UUID | None = None
    total_chunks: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class ChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    metadata_: dict = Field(default_factory=dict, alias="metadata_")

    model_config = {"from_attributes": True, "populate_by_name": True}


class ChunkListResponse(BaseModel):
    chunks: list[ChunkResponse]
    total: int
