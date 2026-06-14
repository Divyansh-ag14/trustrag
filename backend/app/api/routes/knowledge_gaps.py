"""Knowledge gaps — admin review queue for questions the system couldn't answer."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.knowledge_gap import KnowledgeGap
from app.models.user import User
from app.schemas.knowledge_gap import KnowledgeGapResponse, KnowledgeGapUpdate

router = APIRouter(prefix="/knowledge-gaps", tags=["knowledge-gaps"])


@router.get("/", response_model=list[KnowledgeGapResponse])
async def list_knowledge_gaps(
    status_filter: str | None = Query(default=None, alias="status"),
    reason: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeGap).where(KnowledgeGap.workspace_id == user.workspace_id)
    if status_filter:
        query = query.where(KnowledgeGap.status == status_filter)
    if reason:
        query = query.where(KnowledgeGap.reason == reason)
    query = query.order_by(KnowledgeGap.occurrences.desc(), KnowledgeGap.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def knowledge_gap_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(func.count(KnowledgeGap.id)).where(
        KnowledgeGap.workspace_id == user.workspace_id
    )
    total = (await db.execute(base)).scalar() or 0
    open_count = (
        await db.execute(base.where(KnowledgeGap.status == "open"))
    ).scalar() or 0
    resolved = (
        await db.execute(base.where(KnowledgeGap.status == "resolved"))
    ).scalar() or 0

    by_reason_rows = (
        await db.execute(
            select(KnowledgeGap.reason, func.count(KnowledgeGap.id))
            .where(KnowledgeGap.workspace_id == user.workspace_id)
            .group_by(KnowledgeGap.reason)
        )
    ).all()

    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "by_reason": {reason: count for reason, count in by_reason_rows},
    }


@router.get("/{gap_id}", response_model=KnowledgeGapResponse)
async def get_knowledge_gap(
    gap_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    gap = await db.get(KnowledgeGap, gap_id)
    if not gap or gap.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge gap not found")
    return gap


@router.patch("/{gap_id}", response_model=KnowledgeGapResponse)
async def update_knowledge_gap(
    gap_id: uuid.UUID,
    body: KnowledgeGapUpdate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    gap = await db.get(KnowledgeGap, gap_id)
    if not gap or gap.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge gap not found")

    if body.status is not None:
        gap.status = body.status
    if body.assigned_to is not None:
        gap.assigned_to = body.assigned_to
    if body.resolution_notes is not None:
        gap.resolution_notes = body.resolution_notes
    if body.missing_topic is not None:
        gap.missing_topic = body.missing_topic

    await db.flush()
    # onupdate=func.now() expires updated_at; reload it within the async context
    # so response serialization doesn't trigger a lazy load outside greenlet.
    await db.refresh(gap)
    return gap
