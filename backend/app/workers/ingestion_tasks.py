import asyncio
import uuid

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.workers.celery_app import celery_app

logger = structlog.get_logger()

sync_engine = create_engine(settings.DATABASE_SYNC_URL)
SyncSession = sessionmaker(bind=sync_engine)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: str, file_path: str):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.ingestion.processor import process_document

    logger.info("task.process_document.start", document_id=document_id, task_id=self.request.id)

    async def _run():
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            await process_document(session, uuid.UUID(document_id), file_path)
            await session.commit()
        await engine.dispose()

    try:
        _run_async(_run())
        logger.info("task.process_document.complete", document_id=document_id)
    except Exception as exc:
        logger.error("task.process_document.failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc)
