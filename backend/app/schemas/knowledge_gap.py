import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeGapResponse(BaseModel):
    id: uuid.UUID
    query_id: uuid.UUID | None
    question: str
    reason: str
    missing_topic: str | None
    weak_sources: list
    occurrences: int
    status: str
    assigned_to: uuid.UUID | None
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeGapUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|assigned|resolved|dismissed)$")
    assigned_to: uuid.UUID | None = None
    resolution_notes: str | None = None
    missing_topic: str | None = None
