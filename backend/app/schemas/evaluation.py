import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    item_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalItemCreate(BaseModel):
    question: str
    expected_answer: str
    expected_source_docs: list[str] = []
    query_type: str | None = None
    difficulty: str | None = None
    tags: list[str] = []


class EvalItemResponse(BaseModel):
    id: uuid.UUID
    question: str
    expected_answer: str
    expected_source_docs: list[str]
    query_type: str | None
    difficulty: str | None
    tags: list[str]

    model_config = {"from_attributes": True}


class EvalRunCreate(BaseModel):
    dataset_id: uuid.UUID
    name: str | None = None


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    name: str | None
    metrics: dict
    status: str
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EvalRunDetailResponse(EvalRunResponse):
    per_item_results: list[dict]
