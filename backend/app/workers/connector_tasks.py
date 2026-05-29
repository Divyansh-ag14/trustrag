"""Celery tasks for connector sync operations."""

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.connectors.base import FetchedDocument
from app.connectors.encryption import decrypt_credentials
from app.models.connector import Connector
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.ingestion.processor import process_document_from_text
from app.workers.celery_app import celery_app

logger = structlog.get_logger()


def _get_connector_class(connector_type: str):
    """Return the connector class for a given type."""
    from app.connectors.notion_connector import NotionConnector
    from app.connectors.github_connector import GitHubConnector
    from app.connectors.web_scraper import WebScraperConnector

    mapping = {
        "notion": NotionConnector,
        "github": GitHubConnector,
        "web_scraper": WebScraperConnector,
    }
    cls = mapping.get(connector_type)
    if not cls:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return cls


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _sync_connector(connector_id: str) -> dict:
    """Core sync logic: fetch documents and ingest new/changed ones."""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with async_session() as db:
            # Load connector
            result = await db.execute(
                select(Connector).where(Connector.id == uuid.UUID(connector_id))
            )
            connector = result.scalar_one_or_none()
            if not connector:
                raise ValueError(f"Connector {connector_id} not found")

            # Update status
            connector.status = "syncing"
            await db.commit()

            # Decrypt credentials and instantiate connector
            credentials = decrypt_credentials(connector.encrypted_credentials)
            connector_cls = _get_connector_class(connector.connector_type)
            instance = connector_cls(connector, credentials)

            # Fetch documents from source
            fetched_docs = await instance.fetch_documents()

            # Get existing documents for this connector
            existing_result = await db.execute(
                select(Document).where(
                    Document.workspace_id == connector.workspace_id,
                    Document.metadata_["connector_id"].astext == str(connector.id),
                    Document.status == "active",
                )
            )
            existing_docs = {
                doc.content_hash: doc for doc in existing_result.scalars().all()
            }

            new_count = 0
            updated_count = 0
            skipped_count = 0

            for fetched in fetched_docs:
                if fetched.content_hash in existing_docs:
                    # Content unchanged, skip
                    skipped_count += 1
                    continue

                # Check if we have a previous version by source URL
                prev_result = await db.execute(
                    select(Document).where(
                        Document.workspace_id == connector.workspace_id,
                        Document.source_url == fetched.source_url,
                        Document.status == "active",
                    )
                )
                prev_doc = prev_result.scalar_one_or_none()

                if prev_doc:
                    # Archive old version
                    prev_doc.status = "archived"
                    updated_count += 1
                else:
                    new_count += 1

                # Create new document record
                doc = Document(
                    workspace_id=connector.workspace_id,
                    title=fetched.title,
                    source_type=fetched.source_type,
                    source_url=fetched.source_url,
                    content_hash=fetched.content_hash,
                    status="processing",
                    metadata_=fetched.metadata,
                    total_chunks=0,
                )
                db.add(doc)
                await db.flush()

                # Create ingestion job
                job = IngestionJob(
                    workspace_id=connector.workspace_id,
                    document_id=doc.id,
                    status="processing",
                    started_at=datetime.now(timezone.utc),
                )
                db.add(job)
                await db.flush()

                # Process document through existing pipeline
                try:
                    await process_document_from_text(db, doc.id, fetched.content)
                    await db.commit()
                except Exception as e:
                    logger.error(
                        "connector.document_ingest_failed",
                        connector_id=connector_id,
                        title=fetched.title,
                        error=str(e),
                    )
                    await db.rollback()

            # Update connector stats
            async with async_session() as db2:
                result = await db2.execute(
                    select(Connector).where(Connector.id == uuid.UUID(connector_id))
                )
                connector = result.scalar_one()
                connector.status = "active"
                connector.last_synced_at = datetime.now(timezone.utc)
                connector.last_sync_error = None
                connector.documents_synced = (connector.documents_synced or 0) + new_count + updated_count
                await db2.commit()

            summary = {
                "new": new_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_fetched": len(fetched_docs),
            }
            logger.info("connector.sync_complete", connector_id=connector_id, **summary)
            return summary

    except Exception as e:
        # Mark connector as error
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Connector).where(Connector.id == uuid.UUID(connector_id))
                )
                connector = result.scalar_one_or_none()
                if connector:
                    connector.status = "error"
                    connector.last_sync_error = str(e)[:500]
                    await db.commit()
        except Exception:
            pass
        raise
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def sync_connector_task(self, connector_id: str):
    """Celery task: sync a single connector."""
    logger.info("task.sync_connector.start", connector_id=connector_id)
    try:
        result = _run_async(_sync_connector(connector_id))
        logger.info("task.sync_connector.complete", connector_id=connector_id, result=result)
        return result
    except Exception as exc:
        logger.error("task.sync_connector.failed", connector_id=connector_id, error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task
def sync_all_connectors_task():
    """Celery beat task: check all connectors and sync those due for refresh."""

    async def _check_and_sync():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, expire_on_commit=False)

        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Connector).where(
                        Connector.sync_enabled.is_(True),
                        Connector.status.in_(["active", "error"]),
                    )
                )
                connectors = result.scalars().all()

                now = datetime.now(timezone.utc)
                for conn in connectors:
                    if conn.last_synced_at is None:
                        # Never synced — sync now
                        sync_connector_task.delay(str(conn.id))
                    else:
                        hours_since = (now - conn.last_synced_at).total_seconds() / 3600
                        if hours_since >= conn.sync_interval_hours:
                            sync_connector_task.delay(str(conn.id))
        finally:
            await engine.dispose()

    logger.info("task.sync_all_connectors.start")
    _run_async(_check_and_sync())
