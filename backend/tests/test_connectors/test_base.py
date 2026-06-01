"""Tests for base connector and FetchedDocument."""

from app.connectors.base import FetchedDocument


class TestFetchedDocument:
    def test_hash_content(self):
        h1 = FetchedDocument.hash_content("hello world")
        h2 = FetchedDocument.hash_content("hello world")
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex digest

    def test_hash_different_content(self):
        h1 = FetchedDocument.hash_content("content A")
        h2 = FetchedDocument.hash_content("content B")
        assert h1 != h2

    def test_create_fetched_document(self):
        doc = FetchedDocument(
            title="Test Page",
            content="# Hello\n\nSome content.",
            source_url="https://notion.so/page-123",
            source_type="notion",
            content_hash=FetchedDocument.hash_content("# Hello\n\nSome content."),
            metadata={"notion_page_id": "page-123"},
            images=[{"url": "https://example.com/img.png", "alt": "diagram"}],
        )
        assert doc.title == "Test Page"
        assert doc.source_type == "notion"
        assert len(doc.images) == 1
        assert doc.metadata["notion_page_id"] == "page-123"

    def test_default_fields(self):
        doc = FetchedDocument(
            title="Min",
            content="text",
            source_url="http://example.com",
            source_type="web",
            content_hash="abc",
        )
        assert doc.metadata == {}
        assert doc.images == []
