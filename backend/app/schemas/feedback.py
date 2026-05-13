import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    query_result_id: uuid.UUID
    rating: str = Field(pattern="^(up|down)$")
    comment: str | None = None
    corrected_answer: str | None = None


class FeedbackReview(BaseModel):
    review_note: str


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    query_result_id: uuid.UUID
    user_id: uuid.UUID | None
    rating: str
    comment: str | None
    corrected_answer: str | None
    reviewed_by: uuid.UUID | None
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
