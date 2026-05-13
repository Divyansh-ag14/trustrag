import uuid

from sqlalchemy import Float, ForeignKey, Integer, Numeric, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Query(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "queries"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    original_query: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    query_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    workspace = relationship("Workspace", back_populates="queries")
    results = relationship("QueryResult", back_populates="query", cascade="all, delete-orphan")


class QueryResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "query_results"

    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queries.id", ondelete="CASCADE")
    )
    answer: Mapped[str] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    faithfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    hallucination_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    citation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    retrieval_trace: Mapped[dict] = mapped_column(JSONB, default=dict)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    query = relationship("Query", back_populates="results")
    retrieved_chunks = relationship(
        "RetrievedChunk", back_populates="query_result", cascade="all, delete-orphan"
    )
    feedback = relationship("Feedback", back_populates="query_result", cascade="all, delete-orphan")


class RetrievedChunk(UUIDMixin, Base):
    __tablename__ = "retrieved_chunks"

    query_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("query_results.id", ondelete="CASCADE")
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunks.id")
    )
    retrieval_method: Mapped[str] = mapped_column(String(20))
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    bm25_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    freshness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rerank_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float] = mapped_column(Float)
    rank_position: Mapped[int] = mapped_column(Integer)
    was_used_in_context: Mapped[bool] = mapped_column(Boolean, default=False)

    query_result = relationship("QueryResult", back_populates="retrieved_chunks")
