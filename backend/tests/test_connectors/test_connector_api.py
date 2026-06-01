"""Tests for connector API endpoints — CRUD, test, sync."""

import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import Connector
from app.models.user import User
from app.models.workspace import Workspace
from app.connectors.encryption import encrypt_credentials
from tests.conftest import auth_header


@pytest.fixture(autouse=True)
def mock_encryption_key():
    key = Fernet.generate_key().decode()
    with patch("app.connectors.encryption.settings") as mock_settings:
        mock_settings.CONNECTOR_ENCRYPTION_KEY = key
        with patch("app.api.routes.connectors.encrypt_credentials", wraps=encrypt_credentials):
            yield key




@pytest_asyncio.fixture
async def sample_connector(db: AsyncSession, workspace: Workspace, mock_encryption_key) -> Connector:
    with patch("app.connectors.encryption.settings") as mock_settings:
        mock_settings.CONNECTOR_ENCRYPTION_KEY = mock_encryption_key
        encrypted = encrypt_credentials({"token": "test-token"})

    conn = Connector(
        workspace_id=workspace.id,
        name="Test Notion",
        connector_type="notion",
        encrypted_credentials=encrypted,
        config={"page_ids": ["abc123"]},
        sync_enabled=False,
        sync_interval_hours=24,
        status="active",
    )
    db.add(conn)
    await db.flush()
    return conn


class TestListConnectors:
    async def test_list_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/connectors/", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_returns_connectors(
        self, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.get("/api/v1/connectors/", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Notion"
        assert data[0]["connector_type"] == "notion"

    async def test_requires_admin(self, client: AsyncClient, member_user: User):
        resp = await client.get("/api/v1/connectors/", headers=auth_header(member_user))
        assert resp.status_code == 403

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/connectors/")
        assert resp.status_code in (401, 403)


class TestCreateConnector:
    async def test_create_notion(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/connectors/",
            headers=auth_header(admin_user),
            json={
                "name": "My Notion",
                "connector_type": "notion",
                "credentials": {"token": "ntn_abc"},
                "config": {"page_ids": ["page1"]},
                "sync_enabled": True,
                "sync_interval_hours": 12,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Notion"
        assert data["connector_type"] == "notion"
        assert data["sync_enabled"] is True
        assert data["sync_interval_hours"] == 12
        assert data["status"] == "active"

    async def test_create_github(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/connectors/",
            headers=auth_header(admin_user),
            json={
                "name": "My GitHub",
                "connector_type": "github",
                "credentials": {"token": "ghp_abc"},
                "config": {"owner": "acme", "repo": "docs"},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["connector_type"] == "github"

    async def test_create_web_scraper(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/connectors/",
            headers=auth_header(admin_user),
            json={
                "name": "Docs Site",
                "connector_type": "web_scraper",
                "credentials": {},
                "config": {"base_url": "https://docs.example.com", "max_depth": 2},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["connector_type"] == "web_scraper"

    async def test_requires_admin(self, client: AsyncClient, member_user: User):
        resp = await client.post(
            "/api/v1/connectors/",
            headers=auth_header(member_user),
            json={
                "name": "Test",
                "connector_type": "notion",
                "credentials": {"token": "x"},
                "config": {},
            },
        )
        assert resp.status_code == 403


class TestGetConnector:
    async def test_get_existing(
        self, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.get(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Notion"

    async def test_get_not_found(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            f"/api/v1/connectors/{uuid.uuid4()}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    async def test_workspace_isolation(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_connector: Connector,
        admin_user: User,
    ):
        """Can't access connectors from other workspaces."""
        from app.services.auth_service import hash_password

        other_ws = Workspace(name="Other", slug=f"other-{uuid.uuid4().hex[:6]}", settings={})
        db.add(other_ws)
        await db.flush()
        other_user = User(
            workspace_id=other_ws.id,
            email=f"other-{uuid.uuid4().hex[:6]}@test.com",
            name="Other Admin",
            role="admin",
            hashed_password=hash_password("pass"),
        )
        db.add(other_user)
        await db.flush()

        resp = await client.get(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(other_user),
        )
        assert resp.status_code == 404


class TestUpdateConnector:
    async def test_update_name(
        self, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.patch(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(admin_user),
            json={"name": "Updated Notion"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Notion"

    async def test_update_sync_settings(
        self, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.patch(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(admin_user),
            json={"sync_enabled": True, "sync_interval_hours": 6},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_enabled"] is True
        assert data["sync_interval_hours"] == 6

    async def test_update_not_found(self, client: AsyncClient, admin_user: User):
        resp = await client.patch(
            f"/api/v1/connectors/{uuid.uuid4()}",
            headers=auth_header(admin_user),
            json={"name": "x"},
        )
        assert resp.status_code == 404


class TestDeleteConnector:
    async def test_delete_existing(
        self, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.delete(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(
            f"/api/v1/connectors/{sample_connector.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, admin_user: User):
        resp = await client.delete(
            f"/api/v1/connectors/{uuid.uuid4()}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


class TestSyncConnector:
    @patch("app.api.routes.connectors.sync_connector_task")
    async def test_trigger_sync(
        self, mock_task, client: AsyncClient, admin_user: User, sample_connector: Connector,
    ):
        resp = await client.post(
            f"/api/v1/connectors/{sample_connector.id}/sync",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "syncing"
        mock_task.delay.assert_called_once_with(str(sample_connector.id))

    @patch("app.api.routes.connectors.sync_connector_task")
    async def test_sync_already_in_progress(
        self,
        mock_task,
        client: AsyncClient,
        db: AsyncSession,
        admin_user: User,
        sample_connector: Connector,
    ):
        sample_connector.status = "syncing"
        await db.flush()

        resp = await client.post(
            f"/api/v1/connectors/{sample_connector.id}/sync",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 409
