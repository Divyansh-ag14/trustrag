"""Admin API routes — workspace settings, user management, API keys."""

import hashlib
import secrets
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.database import get_db
from app.models.api_key import APIKey
from app.models.user import User
from app.models.workspace import Workspace
from app.services.auth_service import hash_password

logger = structlog.get_logger()

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Workspace ─────────────────────────────────────────────

class WorkspaceUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


@router.get("/workspace")
async def get_workspace(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == user.workspace_id)
    )
    ws = result.scalar_one()
    return {
        "id": str(ws.id),
        "name": ws.name,
        "slug": ws.slug,
        "settings": ws.settings or {},
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
    }


@router.patch("/workspace")
async def update_workspace(
    body: WorkspaceUpdate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Workspace).where(Workspace.id == user.workspace_id)
    )
    ws = result.scalar_one()

    if body.name is not None:
        ws.name = body.name
    if body.settings is not None:
        ws.settings = {**(ws.settings or {}), **body.settings}

    await db.flush()
    return {
        "id": str(ws.id),
        "name": ws.name,
        "slug": ws.slug,
        "settings": ws.settings or {},
    }


# ── Users ─────────────────────────────────────────────────

class InviteUser(BaseModel):
    email: EmailStr
    name: str
    role: str = "member"
    password: str


class UpdateUserRole(BaseModel):
    role: str


@router.get("/users")
async def list_users(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(User.workspace_id == user.workspace_id)
        .order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/users/invite", status_code=201)
async def invite_user(
    body: InviteUser,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    existing = await db.execute(
        select(User).where(
            User.workspace_id == user.workspace_id,
            User.email == body.email,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="User already exists")

    new_user = User(
        workspace_id=user.workspace_id,
        email=body.email,
        name=body.name,
        role=body.role,
        hashed_password=hash_password(body.password),
    )
    db.add(new_user)
    await db.flush()

    return {
        "id": str(new_user.id),
        "email": new_user.email,
        "name": new_user.name,
        "role": new_user.role,
    }


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: uuid.UUID,
    body: UpdateUserRole,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("admin", "member", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.workspace_id == user.workspace_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    target.role = body.role
    await db.flush()

    return {"id": str(target.id), "role": target.role}


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.workspace_id == user.workspace_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(target)
    await db.flush()


# ── API Keys ──────────────────────────────────────────────

class CreateAPIKey(BaseModel):
    name: str
    permissions: list[str] = ["query"]


@router.get("/api-keys")
async def list_api_keys(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey)
        .where(APIKey.workspace_id == user.workspace_id)
        .order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "permissions": k.permissions,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        }
        for k in keys
    ]


@router.post("/api-keys", status_code=201)
async def create_api_key(
    body: CreateAPIKey,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    raw_key = f"tr_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:11]

    api_key = APIKey(
        workspace_id=user.workspace_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=body.name,
        permissions=body.permissions,
    )
    db.add(api_key)
    await db.flush()

    return {
        "id": str(api_key.id),
        "name": api_key.name,
        "key": raw_key,  # Only shown once
        "key_prefix": key_prefix,
        "permissions": api_key.permissions,
    }


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == key_id,
            APIKey.workspace_id == user.workspace_id,
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(key)
    await db.flush()
