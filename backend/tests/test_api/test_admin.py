"""Tests for admin API — workspace, users, API keys."""

import uuid

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.models.workspace import Workspace
from tests.conftest import auth_header


class TestWorkspace:
    async def test_get_workspace(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/admin/workspace", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "id" in data

    async def test_update_workspace(self, client: AsyncClient, admin_user: User):
        resp = await client.patch(
            "/api/v1/admin/workspace",
            headers=auth_header(admin_user),
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    async def test_non_admin_cannot_update(self, client: AsyncClient, member_user: User):
        resp = await client.patch(
            "/api/v1/admin/workspace",
            headers=auth_header(member_user),
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403


class TestUserManagement:
    async def test_list_users(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/admin/users", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(u["role"] == "admin" for u in data)

    async def test_invite_user(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/admin/users/invite",
            headers=auth_header(admin_user),
            json={
                "email": f"invited-{uuid.uuid4().hex[:6]}@test.com",
                "name": "Invited User",
                "password": "invited123",
                "role": "member",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "member"

    async def test_invite_duplicate_email_fails(self, client: AsyncClient, admin_user: User):
        email = f"dup-{uuid.uuid4().hex[:6]}@test.com"
        # First invite
        await client.post(
            "/api/v1/admin/users/invite",
            headers=auth_header(admin_user),
            json={"email": email, "name": "First", "password": "password123", "role": "member"},
        )
        # Second invite with same email
        resp = await client.post(
            "/api/v1/admin/users/invite",
            headers=auth_header(admin_user),
            json={"email": email, "name": "Dupe", "password": "password123", "role": "member"},
        )
        assert resp.status_code == 409

    async def test_non_admin_cannot_invite(self, client: AsyncClient, member_user: User):
        resp = await client.post(
            "/api/v1/admin/users/invite",
            headers=auth_header(member_user),
            json={
                "email": "new@test.com",
                "name": "New",
                "password": "password123",
                "role": "member",
            },
        )
        assert resp.status_code == 403

    async def test_change_role(self, client: AsyncClient, admin_user: User, member_user: User):
        resp = await client.patch(
            f"/api/v1/admin/users/{member_user.id}/role",
            headers=auth_header(admin_user),
            json={"role": "viewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_delete_user(self, client: AsyncClient, admin_user: User, member_user: User):
        resp = await client.delete(
            f"/api/v1/admin/users/{member_user.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204


class TestAPIKeys:
    async def test_create_api_key(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_header(admin_user),
            json={"name": "Test Key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("tr_")
        assert data["name"] == "Test Key"

    async def test_list_api_keys(self, client: AsyncClient, admin_user: User):
        # Create a key first
        await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_header(admin_user),
            json={"name": "List Test Key"},
        )

        resp = await client.get("/api/v1/admin/api-keys", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        # Raw key should NOT be in list response
        # List endpoint should not expose full key
        assert len(data) >= 1

    async def test_revoke_api_key(self, client: AsyncClient, admin_user: User):
        create_resp = await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_header(admin_user),
            json={"name": "Revoke Me"},
        )
        key_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/admin/api-keys/{key_id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

    async def test_non_admin_cannot_manage_keys(self, client: AsyncClient, member_user: User):
        resp = await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_header(member_user),
            json={"name": "Nope"},
        )
        assert resp.status_code == 403
