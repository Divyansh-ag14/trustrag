"""Base connector interface and shared data types."""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models.connector import Connector


@dataclass
class FetchedDocument:
    """A document fetched from an external source, ready for ingestion."""
    title: str
    content: str  # markdown/text content
    source_url: str
    source_type: str  # "notion", "github", "web"
    content_hash: str  # SHA256 for change detection
    metadata: dict = field(default_factory=dict)  # connector-specific fields
    images: list[dict] = field(default_factory=list)  # [{"url": "...", "alt": "...", "data": bytes | None}]

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    def __init__(self, connector: Connector, credentials: dict):
        self.connector = connector
        self.credentials = credentials
        self.config = connector.config or {}

    @abstractmethod
    async def fetch_documents(self) -> list[FetchedDocument]:
        """Fetch all documents from the source.

        Returns list of FetchedDocument ready for ingestion.
        The connector should handle pagination, rate limiting, and retries.
        """

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Verify credentials and connectivity.

        Returns (success: bool, message: str).
        """
