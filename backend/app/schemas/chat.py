import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_id: uuid.UUID | None = None


class CitationDetail(BaseModel):
    index: int
    document_title: str
    chunk_snippet: str
    document_id: uuid.UUID
    relevance_score: float


class ChatResponse(BaseModel):
    query_id: uuid.UUID
    result_id: uuid.UUID
    answer: str
    citations: list[CitationDetail]
    confidence_score: float
    faithfulness_score: float | None = None
    hallucination_score: float | None = None
    citation_accuracy: float | None = None
    status: str
    has_conflicts: bool = False
    follow_up_suggestions: list[str] = []
    latency_breakdown: dict = {}
    token_usage: dict = {}
    cost_usd: float | None = None


class SessionResponse(BaseModel):
    session_id: uuid.UUID
    query_count: int
    last_query_at: str | None = None


class SessionHistoryResponse(BaseModel):
    session_id: uuid.UUID
    messages: list[dict]
