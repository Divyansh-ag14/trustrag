"""Notion connector — fetches pages via Notion API and converts blocks to markdown."""

import re

import structlog
import httpx

from app.connectors.base import BaseConnector, FetchedDocument

logger = structlog.get_logger()

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

_DASHED_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX32 = re.compile(r"[0-9a-fA-F]{32}")


def _normalize_notion_id(raw: str) -> str:
    """Return the 32-char id from a raw id OR a full Notion URL.

    Users routinely paste the whole page/database URL (it ends with the id,
    sometimes dash-formatted as a UUID), so extract the id instead of failing.
    """
    raw = (raw or "").strip()
    m = _DASHED_UUID.search(raw)
    if m:
        return m.group(0)
    m = _HEX32.search(raw)
    if m:
        return m.group(0)
    return raw


class NotionConnector(BaseConnector):
    """Fetch pages from a Notion workspace using an integration token."""

    def _headers(self) -> dict:
        token = (self.credentials or {}).get("token", "").strip()
        return {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    async def test_connection(self) -> tuple[bool, str]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{NOTION_API}/users/me", headers=self._headers())
                if resp.status_code == 200:
                    data = resp.json()
                    bot_name = data.get("name", "Unknown")
                    return True, f"Connected as {bot_name}"
                return False, f"Notion API returned {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    async def fetch_documents(self) -> list[FetchedDocument]:
        # Accept raw ids or full pasted URLs for both pages and database.
        page_ids = [_normalize_notion_id(p) for p in self.config.get("page_ids", [])]
        database_id = self.config.get("database_id")
        if database_id:
            database_id = _normalize_notion_id(database_id)
        documents = []

        async with httpx.AsyncClient(timeout=30) as client:
            # If database_id is provided, query the database for pages
            if database_id:
                db_pages = await self._query_database(client, database_id)
                page_ids = list(set(page_ids + db_pages))

            for page_id in page_ids:
                try:
                    doc = await self._fetch_page(client, page_id)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    logger.warning("notion.page_fetch_failed", page_id=page_id, error=str(e))

        logger.info("notion.fetch_complete", pages_fetched=len(documents))
        return documents

    async def _query_database(self, client: httpx.AsyncClient, database_id: str) -> list[str]:
        """Query a Notion database and return page IDs."""
        page_ids = []
        has_more = True
        start_cursor = None

        while has_more:
            body = {"page_size": 100}
            if start_cursor:
                body["start_cursor"] = start_cursor

            resp = await client.post(
                f"{NOTION_API}/databases/{database_id}/query",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", []):
                page_ids.append(result["id"])

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return page_ids

    async def _fetch_page(self, client: httpx.AsyncClient, page_id: str) -> FetchedDocument | None:
        """Fetch a single page and its blocks, convert to markdown."""
        # Get page metadata
        resp = await client.get(f"{NOTION_API}/pages/{page_id}", headers=self._headers())
        resp.raise_for_status()
        page = resp.json()

        title = self._extract_title(page)
        last_edited = page.get("last_edited_time", "")

        # Get page blocks
        blocks = await self._get_all_blocks(client, page_id)
        content = self._blocks_to_markdown(blocks)

        if not content.strip():
            return None

        images = self._extract_images(blocks)

        return FetchedDocument(
            title=title,
            content=content,
            source_url=f"https://notion.so/{page_id.replace('-', '')}",
            source_type="notion",
            content_hash=FetchedDocument.hash_content(content),
            metadata={
                "notion_page_id": page_id,
                "last_edited_time": last_edited,
                "connector_id": str(self.connector.id),
            },
            images=images,
        )

    async def _get_all_blocks(self, client: httpx.AsyncClient, block_id: str) -> list[dict]:
        """Recursively fetch all blocks for a page."""
        blocks = []
        has_more = True
        start_cursor = None

        while has_more:
            params = {"page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            resp = await client.get(
                f"{NOTION_API}/blocks/{block_id}/children",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for block in data.get("results", []):
                blocks.append(block)
                # Recursively fetch children for blocks that have them
                if block.get("has_children", False):
                    children = await self._get_all_blocks(client, block["id"])
                    block["_children"] = children

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        return blocks

    @staticmethod
    def _extract_title(page: dict) -> str:
        """Extract page title from Notion page properties."""
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_parts = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_parts)
        return "Untitled"

    @staticmethod
    def _rich_text_to_str(rich_text_list: list[dict]) -> str:
        """Convert Notion rich text array to plain string."""
        return "".join(rt.get("plain_text", "") for rt in rich_text_list)

    def _blocks_to_markdown(self, blocks: list[dict], indent: int = 0) -> str:
        """Convert Notion blocks to markdown text."""
        lines = []
        prefix = "  " * indent

        for block in blocks:
            block_type = block.get("type", "")
            data = block.get(block_type, {})

            if block_type == "paragraph":
                text = self._rich_text_to_str(data.get("rich_text", []))
                if text:
                    lines.append(f"{prefix}{text}")
                lines.append("")

            elif block_type.startswith("heading_"):
                level = int(block_type[-1])
                text = self._rich_text_to_str(data.get("rich_text", []))
                lines.append(f"{'#' * level} {text}")
                lines.append("")

            elif block_type == "bulleted_list_item":
                text = self._rich_text_to_str(data.get("rich_text", []))
                lines.append(f"{prefix}- {text}")

            elif block_type == "numbered_list_item":
                text = self._rich_text_to_str(data.get("rich_text", []))
                lines.append(f"{prefix}1. {text}")

            elif block_type == "to_do":
                text = self._rich_text_to_str(data.get("rich_text", []))
                checked = "x" if data.get("checked", False) else " "
                lines.append(f"{prefix}- [{checked}] {text}")

            elif block_type == "toggle":
                text = self._rich_text_to_str(data.get("rich_text", []))
                lines.append(f"{prefix}**{text}**")

            elif block_type == "code":
                text = self._rich_text_to_str(data.get("rich_text", []))
                lang = data.get("language", "")
                lines.append(f"{prefix}```{lang}")
                lines.append(text)
                lines.append(f"{prefix}```")
                lines.append("")

            elif block_type == "quote":
                text = self._rich_text_to_str(data.get("rich_text", []))
                lines.append(f"{prefix}> {text}")
                lines.append("")

            elif block_type == "callout":
                text = self._rich_text_to_str(data.get("rich_text", []))
                emoji = data.get("icon", {}).get("emoji", "")
                lines.append(f"{prefix}> {emoji} {text}")
                lines.append("")

            elif block_type == "divider":
                lines.append(f"{prefix}---")
                lines.append("")

            elif block_type == "table":
                # Tables handled via children
                pass

            elif block_type == "table_row":
                cells = data.get("cells", [])
                row_text = " | ".join(self._rich_text_to_str(cell) for cell in cells)
                lines.append(f"{prefix}| {row_text} |")

            elif block_type == "image":
                # Image blocks are tracked separately
                caption = self._rich_text_to_str(data.get("caption", []))
                if caption:
                    lines.append(f"{prefix}[Image: {caption}]")
                else:
                    lines.append(f"{prefix}[Image]")
                lines.append("")

            # Recurse into children
            children = block.get("_children", [])
            if children:
                child_md = self._blocks_to_markdown(children, indent + 1)
                lines.append(child_md)

        return "\n".join(lines)

    @staticmethod
    def _extract_images(blocks: list[dict]) -> list[dict]:
        """Extract image URLs from blocks."""
        images = []
        for block in blocks:
            if block.get("type") == "image":
                img_data = block.get("image", {})
                url = ""
                if img_data.get("type") == "external":
                    url = img_data.get("external", {}).get("url", "")
                elif img_data.get("type") == "file":
                    url = img_data.get("file", {}).get("url", "")

                if url:
                    caption_parts = img_data.get("caption", [])
                    alt = "".join(c.get("plain_text", "") for c in caption_parts)
                    images.append({"url": url, "alt": alt, "data": None})

            # Check children
            for child in block.get("_children", []):
                if child.get("type") == "image":
                    img_data = child.get("image", {})
                    url = ""
                    if img_data.get("type") == "external":
                        url = img_data.get("external", {}).get("url", "")
                    elif img_data.get("type") == "file":
                        url = img_data.get("file", {}).get("url", "")
                    if url:
                        caption_parts = img_data.get("caption", [])
                        alt = "".join(c.get("plain_text", "") for c in caption_parts)
                        images.append({"url": url, "alt": alt, "data": None})

        return images
