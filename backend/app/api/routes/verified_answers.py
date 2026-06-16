"""Verified answers — admin-approved corrections served to matching queries."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.feedback import Feedback
from app.models.query import Query, QueryResult
from app.models.user import User
from app.models.verified_answer import VerifiedAnswer
from app.schemas.verified_answer import VerifiedAnswerResponse
from app.services.verified_answer_service import create_verified_answer

router = APIRouter(prefix="/verified-answers", tags=["verified-answers"])


@router.get("/", response_model=list[VerifiedAnswerResponse])
async def list_verified_answers(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VerifiedAnswer)
        .where(
            VerifiedAnswer.workspace_id == user.workspace_id,
            VerifiedAnswer.status == "active",
        )
        .order_by(VerifiedAnswer.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/from-feedback/{feedback_id}",
    response_model=VerifiedAnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def approve_feedback_correction(
    feedback_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approve a thumbs-down's corrected answer as a verified answer."""
    feedback = await db.get(Feedback, feedback_id)
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    if not feedback.corrected_answer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This feedback has no corrected answer to approve",
        )

    qr = await db.get(QueryResult, feedback.query_result_id)
    query = await db.get(Query, qr.query_id) if qr else None
    if not query or query.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source query not found")

    va = await create_verified_answer(
        db,
        workspace_id=user.workspace_id,
        question=query.original_query,
        answer=feedback.corrected_answer,
        source_feedback_id=feedback.id,
        created_by=user.id,
    )
    await db.refresh(va)
    return va


@router.delete("/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_verified_answer(
    answer_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    va = await db.get(VerifiedAnswer, answer_id)
    if not va or va.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verified answer not found")
    va.status = "archived"
    await db.flush()
