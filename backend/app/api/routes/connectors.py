"""Connector management API — admin-only CRUD, test, and sync."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role, get_current_user
from app.connectors.encryption import encrypt_credentials, decrypt_credentials
from app.database import get_db
from app.models.connector import Connector
from app.models.user import User
from app.schemas.connector import (
    ConnectorCreate,
    ConnectorResponse,
    ConnectorSyncResponse,
    ConnectorTestResponse,
    ConnectorUpdate,
)
from app.workers.connector_tasks import sync_connector_task

logger = structlog.get_logger()

router = APIRouter(prefix="/connectors", tags=["connectors"])


def _connector_to_response(c: Connector) -> dict:
    return {
        "id": str(c.id),
        "workspace_id": str(c.workspace_id),
        "name": c.name,
        "connector_type": c.connector_type,
        "config": c.config or {},
        "sync_enabled": c.sync_enabled,
        "sync_interval_hours": c.sync_interval_hours,
        "status": c.status,
        "last_synced_at": c.last_synced_at,
        "last_sync_error": c.last_sync_error,
        "documents_synced": c.documents_synced or 0,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("/", response_model=list[ConnectorResponse])
async def list_connectors(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector)
        .where(Connector.workspace_id == user.workspace_id)
        .order_by(Connector.created_at.desc())
    )
    connectors = result.scalars().all()
    return [_connector_to_response(c) for c in connectors]


@router.post("/", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    encrypted = encrypt_credentials(body.credentials)

    connector = Connector(
        workspace_id=user.workspace_id,
        name=body.name,
        connector_type=body.connector_type.value,
        encrypted_credentials=encrypted,
        config=body.config,
        sync_enabled=body.sync_enabled,
        sync_interval_hours=body.sync_interval_hours,
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)

    logger.info("connector.created", connector_id=str(connector.id), type=connector.connector_type)
    return _connector_to_response(connector)


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == user.workspace_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return _connector_to_response(connector)


@router.patch("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == user.workspace_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if body.name is not None:
        connector.name = body.name
    if body.credentials is not None:
        connector.encrypted_credentials = encrypt_credentials(body.credentials)
    if body.config is not None:
        connector.config = body.config
    if body.sync_enabled is not None:
        connector.sync_enabled = body.sync_enabled
    if body.sync_interval_hours is not None:
        connector.sync_interval_hours = body.sync_interval_hours

    await db.commit()
    await db.refresh(connector)
    return _connector_to_response(connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == user.workspace_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    await db.delete(connector)
    await db.commit()
    logger.info("connector.deleted", connector_id=str(connector_id))


@router.post("/{connector_id}/test", response_model=ConnectorTestResponse)
async def test_connector(
    connector_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == user.workspace_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    credentials = decrypt_credentials(connector.encrypted_credentials)

    from app.workers.connector_tasks import _get_connector_class
    connector_cls = _get_connector_class(connector.connector_type)
    instance = connector_cls(connector, credentials)

    success, message = await instance.test_connection()
    return {"success": success, "message": message}


@router.post("/{connector_id}/sync", response_model=ConnectorSyncResponse)
async def trigger_sync(
    connector_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == user.workspace_id,
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if connector.status == "syncing":
        raise HTTPException(status_code=409, detail="Sync already in progress")

    # Dispatch async sync task
    sync_connector_task.delay(str(connector_id))

    logger.info("connector.sync_triggered", connector_id=str(connector_id))
    return {
        "connector_id": str(connector_id),
        "status": "syncing",
        "message": "Sync job dispatched",
    }
