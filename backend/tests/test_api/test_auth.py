"""Tests for auth endpoints — register, login, refresh, me."""

import uuid

from httpx import AsyncClient

from app.models.user import User
from tests.conftest import auth_header


class TestRegister:
    async def test_register_creates_workspace_and_user(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "workspace_name": "New Corp",
            "email": f"new-{uuid.uuid4().hex[:6]}@test.com",
            "name": "New User",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_short_password_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "workspace_name": "Corp",
            "email": "test@test.com",
            "name": "User",
            "password": "short",
        })
        assert resp.status_code == 422

    async def test_register_invalid_email_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "workspace_name": "Corp",
            "email": "not-an-email",
            "name": "User",
            "password": "password123",
        })
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, admin_user: User):
        resp = await client.post("/api/v1/auth/login", json={
            "email": admin_user.email,
            "password": "testpass123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_login_wrong_password(self, client: AsyncClient, admin_user: User):
        resp = await client.post("/api/v1/auth/login", json={
            "email": admin_user.email,
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "password123",
        })
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_returns_new_tokens(self, client: AsyncClient, admin_user: User):
        # First login to get tokens
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": admin_user.email,
            "password": "testpass123",
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_rejects_access_token(self, client: AsyncClient, admin_user: User):
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": admin_user.email,
            "password": "testpass123",
        })
        access_token = login_resp.json()["access_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token,  # access, not refresh
        })
        assert resp.status_code == 401

    async def test_refresh_rejects_garbage(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "garbage.token.here",
        })
        assert resp.status_code in (401, 500)


class TestMe:
    async def test_me_returns_user(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/auth/me", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == admin_user.email
        assert data["role"] == "admin"

    async def test_me_without_token_returns_401_or_403(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    async def test_me_with_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401
