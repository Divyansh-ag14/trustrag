"""Knowledge gap recording — turns failed answers into tracked work items."""

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_gap import KnowledgeGap

logger = structlog.get_logger()


async def record_knowledge_gap(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    question: str,
    reason: str,
    query_id: uuid.UUID | None = None,
    weak_sources: list | None = None,
) -> KnowledgeGap:
    """Record a knowledge gap for a question the system couldn't answer reliably.

    Deduplicates: if an OPEN gap with the same question already exists for the
    workspace, bump its occurrence count instead of creating a flood of rows.
    """
    normalized = question.strip()

    existing = (
        await db.execute(
            select(KnowledgeGap)
            .where(
                KnowledgeGap.workspace_id == workspace_id,
                func.lower(KnowledgeGap.question) == normalized.lower(),
                KnowledgeGap.status == "open",
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing:
        existing.occurrences += 1
        await db.flush()
        logger.info("knowledge_gap.incremented", gap_id=str(existing.id), occurrences=existing.occurrences)
        return existing

    gap = KnowledgeGap(
        workspace_id=workspace_id,
        query_id=query_id,
        question=normalized,
        reason=reason,
        weak_sources=weak_sources or [],
    )
    db.add(gap)
    await db.flush()
    logger.info("knowledge_gap.created", gap_id=str(gap.id), reason=reason)
    return gap
