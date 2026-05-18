"""Feedback API routes — submit ratings, list, and admin review."""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.feedback import Feedback
from app.models.query import Query, QueryResult
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackReview

logger = structlog.get_logger()

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify the query result exists and belongs to user's workspace
    qr = await db.get(QueryResult, body.query_result_id)
    if not qr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query result not found",
        )

    feedback = Feedback(
        query_result_id=body.query_result_id,
        user_id=user.id,
        rating=body.rating,
        comment=body.comment,
        corrected_answer=body.corrected_answer,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    logger.info(
        "feedback.submitted",
        feedback_id=str(feedback.id),
        rating=body.rating,
        has_comment=bool(body.comment),
    )

    return feedback


@router.get("/", response_model=list[FeedbackResponse])
async def list_feedback(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rating: str | None = Query(None, pattern="^(up|down)$"),
    reviewed: bool | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    query = (
        select(Feedback)
        .join(QueryResult, Feedback.query_result_id == QueryResult.id)
        .join(Query, QueryResult.query_id == Query.id)
        .where(Query.workspace_id == user.workspace_id)
        .order_by(desc(Feedback.created_at))
    )

    if rating:
        query = query.where(Feedback.rating == rating)

    if reviewed is True:
        query = query.where(Feedback.reviewed_at.isnot(None))
    elif reviewed is False:
        query = query.where(Feedback.reviewed_at.is_(None))

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/stats")
async def feedback_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get feedback counts by rating and review status."""
    result = await db.execute(
        select(
            func.count(Feedback.id).label("total"),
            func.count(Feedback.id).filter(Feedback.rating == "up").label("positive"),
            func.count(Feedback.id).filter(Feedback.rating == "down").label("negative"),
            func.count(Feedback.id).filter(Feedback.reviewed_at.isnot(None)).label("reviewed"),
            func.count(Feedback.id).filter(Feedback.reviewed_at.is_(None)).label("unreviewed"),
        )
    )
    row = result.one()
    return {
        "total": row.total,
        "positive": row.positive,
        "negative": row.negative,
        "reviewed": row.reviewed,
        "unreviewed": row.unreviewed,
    }


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback = await db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )
    return feedback


@router.patch("/{feedback_id}/review", response_model=FeedbackResponse)
async def review_feedback(
    feedback_id: uuid.UUID,
    body: FeedbackReview,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback = await db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found",
        )

    feedback.reviewed_by = user.id
    feedback.review_note = body.review_note
    feedback.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(feedback)

    logger.info("feedback.reviewed", feedback_id=str(feedback_id))

    return feedback
