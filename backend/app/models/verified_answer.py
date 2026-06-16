import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class VerifiedAnswer(UUIDMixin, TimestampMixin, Base):
    """An admin-approved answer to a question, served directly to matching queries.

    Created when an admin approves a thumbs-down correction. Closes the
    feedback→quality loop: human-vetted answers are reused, never the AI
    inventing them.
    """

    __tablename__ = "verified_answers"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    # 1536-dim embedding of the question, for semantic matching of new queries
    question_embedding: Mapped[list] = mapped_column(JSONB)
    source_feedback_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | archived
