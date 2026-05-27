"""Tests for file upload validation — filename sanitization, magic bytes, size."""

import pytest

from app.utils.file_validation import (
    validate_file_content,
    validate_file_size,
    validate_filename,
)


class TestValidateFilename:
    def test_normal_filename(self):
        assert validate_filename("report.pdf") == "report.pdf"

    def test_path_traversal_unix(self):
        result = validate_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_path_traversal_windows(self):
        result = validate_filename("..\\..\\windows\\system32\\config")
        assert ".." not in result

    def test_null_bytes_stripped(self):
        result = validate_filename("file\x00.pdf")
        assert "\x00" not in result

    def test_multiple_dots_collapsed(self):
        result = validate_filename("file...pdf")
        assert "..." not in result

    def test_hidden_file_renamed(self):
        result = validate_filename(".htaccess")
        assert not result.startswith(".")

    def test_empty_filename(self):
        result = validate_filename("")
        assert len(result) > 0

    def test_long_filename_truncated(self):
        long_name = "a" * 300 + ".pdf"
        result = validate_filename(long_name)
        assert len(result) <= 255

    def test_preserves_extension(self):
        result = validate_filename("my-document.md")
        assert result.endswith(".md")

    def test_nested_path(self):
        result = validate_filename("/home/user/docs/file.txt")
        assert result == "file.txt"


class TestValidateFileContent:
    def test_pdf_valid(self):
        content = b"%PDF-1.4 some pdf content here"
        assert validate_file_content(content, "pdf") is True

    def test_pdf_invalid_magic(self):
        content = b"this is not a pdf"
        assert validate_file_content(content, "pdf") is False

    def test_html_doctype(self):
        content = b"<!DOCTYPE html><html><body>test</body></html>"
        assert validate_file_content(content, "html") is True

    def test_html_tag(self):
        content = b"<html><body>test</body></html>"
        assert validate_file_content(content, "html") is True

    def test_html_invalid(self):
        content = b"just plain text"
        assert validate_file_content(content, "html") is False

    def test_markdown_skips_check(self):
        content = b"random bytes that are not markdown"
        assert validate_file_content(content, "markdown") is True

    def test_text_skips_check(self):
        assert validate_file_content(b"anything", "text") is True

    def test_csv_skips_check(self):
        assert validate_file_content(b"anything", "csv") is True

    def test_faq_skips_check(self):
        assert validate_file_content(b"anything", "faq") is True

    def test_slack_export_skips_check(self):
        assert validate_file_content(b"anything", "slack_export") is True

    def test_unknown_type_passes(self):
        assert validate_file_content(b"anything", "unknown_format") is True


class TestValidateFileSize:
    def test_within_limit(self):
        assert validate_file_size(1024, max_mb=1) is True

    def test_at_limit(self):
        assert validate_file_size(50 * 1024 * 1024, max_mb=50) is True

    def test_over_limit(self):
        assert validate_file_size(51 * 1024 * 1024, max_mb=50) is False

    def test_zero_size(self):
        assert validate_file_size(0, max_mb=50) is True
