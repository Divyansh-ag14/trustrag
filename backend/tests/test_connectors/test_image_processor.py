"""Tests for GPT-4o vision image processor."""

from unittest.mock import patch, MagicMock

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.image_processor import (
    _describe_image_from_bytes,
    _describe_image_from_url,
    process_images,
    MAX_IMAGES_PER_DOCUMENT,
)
from app.models.document import Document
from app.models.workspace import Workspace
from app.models.user import User


class TestDescribeImageFromBytes:
    @patch("app.ingestion.image_processor._get_client")
    def test_returns_description(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="A diagram showing data flow."))]
        mock_client.return_value.chat.completions.create.return_value = mock_response

        # Minimal PNG bytes (magic header)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = _describe_image_from_bytes(png_bytes, "architecture docs")

        assert result == "A diagram showing data flow."
        mock_client.return_value.chat.completions.create.assert_called_once()

    @patch("app.ingestion.image_processor._get_client")
    def test_returns_none_on_failure(self, mock_client):
        mock_client.return_value.chat.completions.create.side_effect = Exception("API error")

        result = _describe_image_from_bytes(b"\x89PNG" + b"\x00" * 50)
        assert result is None

    @patch("app.ingestion.image_processor._get_client")
    def test_detects_jpeg(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Photo"))]
        mock_client.return_value.chat.completions.create.return_value = mock_response

        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        _describe_image_from_bytes(jpeg_bytes)

        call_args = mock_client.return_value.chat.completions.create.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        # Verify JPEG mime type was used
        user_msg = [m for m in messages if m["role"] == "user"][0]
        img_part = [p for p in user_msg["content"] if p["type"] == "image_url"][0]
        assert "image/jpeg" in img_part["image_url"]["url"]


class TestDescribeImageFromUrl:
    @patch("app.ingestion.image_processor._get_client")
    def test_returns_description(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="A screenshot."))]
        mock_client.return_value.chat.completions.create.return_value = mock_response

        result = _describe_image_from_url("https://example.com/img.png", "page context")
        assert result == "A screenshot."

    @patch("app.ingestion.image_processor._get_client")
    def test_returns_none_on_failure(self, mock_client):
        mock_client.return_value.chat.completions.create.side_effect = Exception("timeout")
        result = _describe_image_from_url("https://example.com/img.png")
        assert result is None


class TestProcessImages:
    @pytest_asyncio.fixture
    async def doc_for_images(self, db: AsyncSession, workspace: Workspace, admin_user: User) -> Document:
        doc = Document(
            workspace_id=workspace.id,
            title="Image Test Doc",
            source_type="notion",
            status="active",
            uploaded_by=admin_user.id,
            total_chunks=0,
        )
        db.add(doc)
        await db.flush()
        return doc

    @patch("app.ingestion.image_processor._describe_image_from_url")
    @patch("app.ingestion.image_processor._describe_image_from_bytes")
    async def test_creates_chunks_from_url_images(
        self, mock_bytes, mock_url, db: AsyncSession, doc_for_images: Document,
    ):
        mock_url.return_value = "Description of the diagram."
        mock_bytes.return_value = None

        images = [
            {"url": "https://example.com/img1.png", "alt": "Architecture", "context": "System design"},
            {"url": "https://example.com/img2.png", "alt": "", "context": ""},
        ]

        count = await process_images(db, doc_for_images.id, images, "Test Doc")
        assert count == 2

    @patch("app.ingestion.image_processor._describe_image_from_url")
    @patch("app.ingestion.image_processor._describe_image_from_bytes")
    async def test_creates_chunks_from_bytes(
        self, mock_bytes, mock_url, db: AsyncSession, doc_for_images: Document,
    ):
        mock_bytes.return_value = "Chart showing monthly revenue."
        mock_url.return_value = None

        images = [
            {"data": b"\x89PNG" + b"\x00" * 50, "url": "", "alt": "Revenue chart", "context": "Q4 report"},
        ]

        count = await process_images(db, doc_for_images.id, images, "Report")
        assert count == 1

    async def test_empty_images(self, db: AsyncSession, doc_for_images: Document):
        count = await process_images(db, doc_for_images.id, [], "Doc")
        assert count == 0

    @patch("app.ingestion.image_processor._describe_image_from_url")
    @patch("app.ingestion.image_processor._describe_image_from_bytes")
    async def test_skips_failed_descriptions(
        self, mock_bytes, mock_url, db: AsyncSession, doc_for_images: Document,
    ):
        mock_url.return_value = None
        mock_bytes.return_value = None

        images = [{"url": "https://example.com/broken.png", "alt": "", "context": ""}]
        count = await process_images(db, doc_for_images.id, images, "Doc")
        assert count == 0

    @patch("app.ingestion.image_processor._describe_image_from_url")
    async def test_caps_at_max_images(
        self, mock_url, db: AsyncSession, doc_for_images: Document,
    ):
        mock_url.return_value = "Description"

        images = [{"url": f"https://example.com/img{i}.png", "alt": "", "context": ""} for i in range(30)]
        count = await process_images(db, doc_for_images.id, images, "Doc")
        assert count == MAX_IMAGES_PER_DOCUMENT

    @patch("app.ingestion.image_processor._describe_image_from_url")
    async def test_chunk_metadata(
        self, mock_url, db: AsyncSession, doc_for_images: Document,
    ):
        mock_url.return_value = "A workflow diagram."

        images = [{"url": "https://example.com/img.png", "alt": "Workflow", "context": "Process docs"}]
        count = await process_images(db, doc_for_images.id, images, "Doc", start_chunk_index=500)
        assert count == 1
