"""Tests for connector passthrough parsers."""

import tempfile
import os

from app.ingestion.parsers.notion_parser import NotionParser
from app.ingestion.parsers.github_parser import GitHubParser
from app.ingestion.parsers.web_parser import WebParser
from app.ingestion.parsers import PARSERS


class TestNotionParser:
    def test_reads_file(self):
        content = "# Notion Page\n\nThis is content from Notion."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = NotionParser.parse(path)
            assert result == content
        finally:
            os.unlink(path)

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("  hello  \n\n")
            path = f.name
        try:
            result = NotionParser.parse(path)
            assert result == "hello"
        finally:
            os.unlink(path)


class TestGitHubParser:
    def test_reads_file(self):
        content = "# README\n\nGitHub repo docs."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = GitHubParser.parse(path)
            assert result == content
        finally:
            os.unlink(path)


class TestWebParser:
    def test_reads_file(self):
        content = "Web page content extracted by scraper."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            result = WebParser.parse(path)
            assert result == content
        finally:
            os.unlink(path)


class TestParsersRegistry:
    def test_notion_registered(self):
        assert "notion" in PARSERS
        assert PARSERS["notion"] is NotionParser

    def test_github_registered(self):
        assert "github" in PARSERS
        assert PARSERS["github"] is GitHubParser

    def test_web_registered(self):
        assert "web" in PARSERS
        assert PARSERS["web"] is WebParser

    def test_all_source_types(self):
        expected = {"pdf", "markdown", "text", "html", "csv", "faq", "slack_export", "notion", "github", "web"}
        assert expected.issubset(set(PARSERS.keys()))
