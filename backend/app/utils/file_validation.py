"""File upload validation — magic bytes, size, and path traversal checks."""

import re
from pathlib import Path

# Magic byte signatures for allowed file types
MAGIC_BYTES = {
    "pdf": [b"%PDF"],
    "html": [b"<!DOCTYPE", b"<!doctype", b"<html", b"<HTML"],
}

# File types that are plain text (no magic byte check needed)
TEXT_TYPES = {"markdown", "text", "csv", "faq", "slack_export"}

MAX_FILENAME_LENGTH = 255


def validate_filename(filename: str) -> str:
    """Sanitize filename, strip path traversal attempts."""
    name = Path(filename).name

    # Remove any path separators that survived
    name = name.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    name = name.replace("\x00", "")

    # Collapse multiple dots
    name = re.sub(r"\.{2,}", ".", name)

    # Truncate
    if len(name) > MAX_FILENAME_LENGTH:
        stem = Path(name).stem[:MAX_FILENAME_LENGTH - 10]
        name = stem + Path(name).suffix

    if not name or name.startswith("."):
        name = "upload" + Path(filename).suffix

    return name


def validate_file_content(content: bytes, source_type: str) -> bool:
    """Check magic bytes for file types that have them."""
    if source_type in TEXT_TYPES:
        return True

    signatures = MAGIC_BYTES.get(source_type)
    if not signatures:
        return True

    header = content[:20]
    return any(header.startswith(sig) for sig in signatures)


def validate_file_size(size: int, max_mb: int) -> bool:
    """Check file doesn't exceed max size."""
    return size <= max_mb * 1024 * 1024
