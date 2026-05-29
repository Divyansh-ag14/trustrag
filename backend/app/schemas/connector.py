"""Pydantic schemas for connector API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConnectorType(str, Enum):
    notion = "notion"
    github = "github"
    web_scraper = "web_scraper"


class ConnectorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    connector_type: ConnectorType
    credentials: dict = Field(..., description="API token / auth credentials (stored encrypted)")
    config: dict = Field(default_factory=dict, description="Non-secret connector configuration")
    sync_enabled: bool = False
    sync_interval_hours: int = Field(default=24, ge=1, le=168)


class ConnectorUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    credentials: dict | None = None
    config: dict | None = None
    sync_enabled: bool | None = None
    sync_interval_hours: int | None = Field(None, ge=1, le=168)


class ConnectorResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    connector_type: str
    config: dict
    sync_enabled: bool
    sync_interval_hours: int
    status: str
    last_synced_at: datetime | None
    last_sync_error: str | None
    documents_synced: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorSyncResponse(BaseModel):
    connector_id: str
    status: str
    message: str


class ConnectorTestResponse(BaseModel):
    success: bool
    message: str
