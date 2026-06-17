"""Tests for document parsers."""

import tempfile

from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.text_parser import TextParser


class TestMarkdownParser:
    def test_parses_plain_markdown(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nSome content.\n\n## Section\n\nMore content.")
            f.flush()
            result = MarkdownParser.parse(f.name)

        assert "Title" in result
        assert "Some content." in result
        assert "Section" in result

    def test_strips_image_links(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Text before ![alt](image.png) text after.")
            f.flush()
            result = MarkdownParser.parse(f.name)

        assert "image.png" not in result
        assert "Text before" in result
        assert "text after" in result

    def test_converts_links_to_text(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Click [here](https://example.com) for docs.")
            f.flush()
            result = MarkdownParser.parse(f.name)

        assert "https://example.com" not in result
        assert "here" in result

    def test_preserves_code_blocks(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("```python\ndef foo():\n    pass\n```")
            f.flush()
            result = MarkdownParser.parse(f.name)

        assert "def foo" in result

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            f.flush()
            result = MarkdownParser.parse(f.name)

        assert result == ""


class TestTextParser:
    def test_parses_plain_text(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, this is plain text.\nSecond line.")
            f.flush()
            result = TextParser.parse(f.name)

        assert "Hello, this is plain text." in result
        assert "Second line." in result

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("  \n  content here  \n  ")
            f.flush()
            result = TextParser.parse(f.name)

        assert result == "content here"

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            f.flush()
            result = TextParser.parse(f.name)

        assert result == ""
