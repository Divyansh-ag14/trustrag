"""Evaluation API routes — dataset CRUD, run triggers, and results."""

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.evaluation import EvaluationDataset, EvaluationItem, EvaluationRun
from app.models.user import User
from app.schemas.evaluation import (
    DatasetCreate,
    DatasetResponse,
    EvalItemCreate,
    EvalItemResponse,
    EvalRunCreate,
    EvalRunDetailResponse,
    EvalRunResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# --- Datasets ---


@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = EvaluationDataset(
        workspace_id=user.workspace_id,
        name=body.name,
        description=body.description,
        item_count=0,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvaluationDataset)
        .where(EvaluationDataset.workspace_id == user.workspace_id)
        .order_by(EvaluationDataset.created_at.desc())
    )
    return result.scalars().all()


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_workspace_dataset(db, dataset_id, user.workspace_id)
    return dataset


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_workspace_dataset(db, dataset_id, user.workspace_id)
    await db.delete(dataset)
    await db.commit()


# --- Items ---


@router.post(
    "/datasets/{dataset_id}/items",
    response_model=list[EvalItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_items(
    dataset_id: uuid.UUID,
    items: list[EvalItemCreate],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_workspace_dataset(db, dataset_id, user.workspace_id)

    created = []
    for item_data in items:
        item = EvaluationItem(
            dataset_id=dataset.id,
            question=item_data.question,
            expected_answer=item_data.expected_answer,
            expected_source_docs=item_data.expected_source_docs,
            query_type=item_data.query_type,
            difficulty=item_data.difficulty,
            tags=item_data.tags,
        )
        db.add(item)
        created.append(item)

    dataset.item_count = dataset.item_count + len(items)
    await db.commit()

    for item in created:
        await db.refresh(item)

    return created


@router.get("/datasets/{dataset_id}/items", response_model=list[EvalItemResponse])
async def list_items(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    await _get_workspace_dataset(db, dataset_id, user.workspace_id)

    result = await db.execute(
        select(EvaluationItem)
        .where(EvaluationItem.dataset_id == dataset_id)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


# --- Runs ---


@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    body: EvalRunCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dataset = await _get_workspace_dataset(db, body.dataset_id, user.workspace_id)

    if dataset.item_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dataset has no evaluation items",
        )

    run = EvaluationRun(
        workspace_id=user.workspace_id,
        dataset_id=dataset.id,
        name=body.name or f"Run {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
        status="queued",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(
        _run_evaluation_background,
        run_id=run.id,
        dataset_id=dataset.id,
        workspace_id=user.workspace_id,
    )

    return run


@router.get("/runs", response_model=list[EvalRunResponse])
async def list_runs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    dataset_id: uuid.UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    query = (
        select(EvaluationRun)
        .where(EvaluationRun.workspace_id == user.workspace_id)
        .order_by(EvaluationRun.started_at.desc())
        .limit(limit)
    )
    if dataset_id:
        query = query.where(EvaluationRun.dataset_id == dataset_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=EvalRunDetailResponse)
async def get_run_detail(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(EvaluationRun, run_id)
    if not run or run.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


# --- Helpers ---


async def _get_workspace_dataset(
    db: AsyncSession, dataset_id: uuid.UUID, workspace_id: uuid.UUID
) -> EvaluationDataset:
    dataset = await db.get(EvaluationDataset, dataset_id)
    if not dataset or dataset.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    return dataset


async def _run_evaluation_background(
    run_id: uuid.UUID, dataset_id: uuid.UUID, workspace_id: uuid.UUID
):
    """Background task that runs the evaluation in a fresh DB session."""
    from app.database import async_session_factory
    from app.evaluation.runner import run_evaluation

    async with async_session_factory() as db:
        try:
            await run_evaluation(db, run_id, dataset_id, workspace_id)
            await db.commit()
        except Exception as e:
            logger.error("evaluation.background_failed", run_id=str(run_id), error=str(e))
            await db.rollback()

            run = await db.get(EvaluationRun, run_id)
            if run:
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
