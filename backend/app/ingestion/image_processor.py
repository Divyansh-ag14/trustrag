"""GPT-4o vision image description for knowledge base indexing.

Extracts text descriptions from images (from connectors or PDFs),
creates DocumentChunk records so they participate in hybrid search.
"""

import base64
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chunk import DocumentChunk

logger = structlog.get_logger()

MAX_IMAGES_PER_DOCUMENT = 20

VISION_SYSTEM_PROMPT = (
    "You are a knowledge base indexer. Describe this image in detail so it can be "
    "found via text search. Include: what the image shows, any text visible in it, "
    "data points, labels, relationships between elements, and key takeaways. "
    "Be factual and thorough. Do not speculate beyond what is visible."
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def _download_image(url: str) -> bytes | None:
    """Download image from URL, return bytes or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except Exception as e:
        logger.warning("image_processor.download_failed", url=url[:100], error=str(e))
        return None


def _describe_image_from_bytes(image_data: bytes, context: str = "") -> str | None:
    """Send image bytes to GPT-4o vision and get text description."""
    client = _get_client()
    b64 = base64.b64encode(image_data).decode("utf-8")

    # Detect mime type from magic bytes
    mime = "image/png"
    if image_data[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    elif image_data[:4] == b"\x89PNG":
        mime = "image/png"
    elif image_data[:4] == b"GIF8":
        mime = "image/gif"
    elif image_data[:4] == b"RIFF":
        mime = "image/webp"

    user_content = []
    if context:
        user_content.append({
            "type": "text",
            "text": f"Context: This image appears in a document about: {context}",
        })
    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=500,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("image_processor.vision_failed", error=str(e))
        return None


def _describe_image_from_url(url: str, context: str = "") -> str | None:
    """Send image URL directly to GPT-4o vision."""
    client = _get_client()

    user_content = []
    if context:
        user_content.append({
            "type": "text",
            "text": f"Context: This image appears in a document about: {context}",
        })
    user_content.append({
        "type": "image_url",
        "image_url": {"url": url, "detail": "high"},
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": VISION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=500,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.warning("image_processor.vision_url_failed", url=url[:100], error=str(e))
        return None


async def process_images(
    db: AsyncSession,
    document_id: uuid.UUID,
    images: list[dict],
    document_title: str = "",
    start_chunk_index: int = 1000,
) -> int:
    """Process images with GPT-4o vision. Returns number of image chunks created.

    Args:
        db: Database session
        document_id: Parent document ID
        images: List of image dicts with keys:
            - data: bytes | None (raw image bytes)
            - url: str (image URL, used if data is None)
            - alt: str (alt text)
            - context: str (surrounding text context)
        document_title: Title of parent document for context
        start_chunk_index: Starting chunk index for image chunks (high to avoid collision)

    Returns:
        Number of image description chunks created
    """
    if not images:
        return 0

    # Cap images per document
    images = images[:MAX_IMAGES_PER_DOCUMENT]
    chunks_created = 0

    for i, image in enumerate(images):
        image_data = image.get("data")
        image_url = image.get("url", "")
        alt_text = image.get("alt", "")
        context = image.get("context", document_title)

        description = None

        # Try bytes first, then URL
        if image_data and isinstance(image_data, bytes):
            description = _describe_image_from_bytes(image_data, context)
        elif image_url:
            description = _describe_image_from_url(image_url, context)

        if not description:
            logger.info(
                "image_processor.skipped",
                document_id=str(document_id),
                image_index=i,
                reason="no description generated",
            )
            continue

        # Build chunk content with alt text prefix if available
        content_parts = []
        if alt_text:
            content_parts.append(f"[Image: {alt_text}]")
        content_parts.append(description)
        chunk_content = "\n".join(content_parts)

        # Create document chunk
        db_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=start_chunk_index + i,
            content=chunk_content,
            token_count=len(chunk_content.split()),  # rough estimate
            metadata_={
                "is_image_description": True,
                "image_source": image_url or "embedded",
                "original_alt": alt_text,
                "image_index": i,
            },
        )
        db.add(db_chunk)
        chunks_created += 1

        logger.info(
            "image_processor.chunk_created",
            document_id=str(document_id),
            image_index=i,
            content_length=len(chunk_content),
        )

    if chunks_created:
        await db.flush()
        logger.info(
            "image_processor.complete",
            document_id=str(document_id),
            images_processed=len(images),
            chunks_created=chunks_created,
        )

    return chunks_created
