import uuid
from datetime import datetime

from pydantic import BaseModel


class VerifiedAnswerResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    source_feedback_id: uuid.UUID | None
    created_by: uuid.UUID | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
