import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class KnowledgeGap(UUIDMixin, TimestampMixin, Base):
    """A question the system could not answer reliably — turned into a tracked work item.

    Auto-created when the pipeline returns no_answer / low_confidence / blocked, so
    failed answers become product value (admins can see what knowledge is missing).
    """

    __tablename__ = "knowledge_gaps"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queries.id", ondelete="SET NULL"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text)
    # no_answer | low_confidence | hallucination_blocked
    reason: Mapped[str] = mapped_column(String(30))
    missing_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    # weak/irrelevant sources that were retrieved, if any: [{title, score}]
    weak_sources: Mapped[list] = mapped_column(JSONB, default=list)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    # open | assigned | resolved | dismissed
    status: Mapped[str] = mapped_column(String(20), default="open")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
