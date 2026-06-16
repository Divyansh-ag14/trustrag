"""Verified answers — reuse admin-approved answers for matching queries.

Closes the feedback→quality loop safely: only human-approved corrections are
stored and served, never AI-invented content.
"""

import math
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embedder import embed_single
from app.models.verified_answer import VerifiedAnswer

logger = structlog.get_logger()

# Cosine similarity above which an incoming query is treated as the same
# question as a verified answer. text-embedding-3-small near-duplicates ~0.9+.
MATCH_THRESHOLD = 0.88


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def create_verified_answer(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    question: str,
    answer: str,
    source_feedback_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
) -> VerifiedAnswer:
    """Embed the question and store an admin-approved answer."""
    embedding = embed_single(question)
    va = VerifiedAnswer(
        workspace_id=workspace_id,
        question=question.strip(),
        answer=answer.strip(),
        question_embedding=embedding,
        source_feedback_id=source_feedback_id,
        created_by=created_by,
    )
    db.add(va)
    await db.flush()
    logger.info("verified_answer.created", id=str(va.id))
    return va


async def match_verified_answer(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    query: str,
    threshold: float = MATCH_THRESHOLD,
) -> tuple[VerifiedAnswer, float] | None:
    """Return (verified_answer, score) if a stored question matches the query."""
    count = (
        await db.execute(
            select(func.count(VerifiedAnswer.id)).where(
                VerifiedAnswer.workspace_id == workspace_id,
                VerifiedAnswer.status == "active",
            )
        )
    ).scalar() or 0
    if count == 0:
        return None  # skip the embed call entirely when there's nothing to match

    query_vec = embed_single(query)

    rows = (
        await db.execute(
            select(VerifiedAnswer).where(
                VerifiedAnswer.workspace_id == workspace_id,
                VerifiedAnswer.status == "active",
            )
        )
    ).scalars().all()

    best: VerifiedAnswer | None = None
    best_score = 0.0
    for va in rows:
        score = _cosine(query_vec, va.question_embedding)
        if score > best_score:
            best, best_score = va, score

    if best and best_score >= threshold:
        logger.info("verified_answer.matched", id=str(best.id), score=round(best_score, 4))
        return best, best_score
    return None
