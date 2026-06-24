"""Tests for document API — list, get, upload validation, delete, chunks."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.user import User
from tests.conftest import auth_header


class TestListDocuments:
    async def test_list_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/documents", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == []
        assert data["total"] == 0

    async def test_list_returns_documents(
        self, client: AsyncClient, admin_user: User, sample_document: Document,
    ):
        resp = await client.get("/api/v1/documents", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["documents"][0]["title"] == "Test Document"

    async def test_list_filters_by_status(
        self, client: AsyncClient, admin_user: User, sample_document: Document,
    ):
        resp = await client.get(
            "/api/v1/documents?status_filter=processing",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0  # sample_document is "active"

        resp = await client.get(
            "/api/v1/documents?status_filter=active",
            headers=auth_header(admin_user),
        )
        assert resp.json()["total"] == 1

    async def test_list_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/documents")
        assert resp.status_code in (401, 403)

    async def test_workspace_isolation(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_document: Document,
        admin_user: User,
    ):
        """Documents from other workspaces should not be visible."""
        from app.models.workspace import Workspace

        other_ws = Workspace(name="Other", slug=f"other-{uuid.uuid4().hex[:6]}", settings={})
        db.add(other_ws)
        await db.flush()
        other_user = User(
            workspace_id=other_ws.id,
            email=f"other-{uuid.uuid4().hex[:6]}@test.com",
            name="Other",
            role="admin",
            hashed_password="hash",
        )
        db.add(other_user)
        await db.flush()

        resp = await client.get("/api/v1/documents", headers=auth_header(other_user))
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestGetDocument:
    async def test_get_existing(
        self, client: AsyncClient, admin_user: User, sample_document: Document,
    ):
        resp = await client.get(
            f"/api/v1/documents/{sample_document.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Document"

    async def test_get_nonexistent(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            f"/api/v1/documents/{uuid.uuid4()}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


class TestUploadValidation:
    async def test_rejects_unsupported_extension(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers=auth_header(admin_user),
            files={"file": ("malware.exe", b"bad content", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    async def test_rejects_fake_pdf(self, client: AsyncClient, admin_user: User):
        """A .pdf file that doesn't start with %PDF should be rejected."""
        resp = await client.post(
            "/api/v1/documents/upload",
            headers=auth_header(admin_user),
            files={"file": ("fake.pdf", b"this is not a pdf", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "content does not match" in resp.json()["detail"]

    async def test_viewer_cannot_upload(self, client: AsyncClient, viewer_user: User):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers=auth_header(viewer_user),
            files={"file": ("doc.md", b"# Test", "text/markdown")},
        )
        assert resp.status_code == 403


class TestListChunks:
    async def test_list_chunks(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_document: Document,
        sample_chunks: list[DocumentChunk],
    ):
        resp = await client.get(
            f"/api/v1/documents/{sample_document.id}/chunks",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["chunks"]) == 2

    async def test_chunks_for_nonexistent_doc(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            f"/api/v1/documents/{uuid.uuid4()}/chunks",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
