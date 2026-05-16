"""Seed script to ingest sample documents into the knowledge base.

Usage:
    cd backend
    python scripts/seed_data.py
"""

import asyncio
import os
import sys
from pathlib import Path

# add backend to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.base import Base
from app.models.workspace import Workspace
from app.models.user import User
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.ingestion.processor import process_document


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_data"

DOCUMENT_SOURCES = [
    ("product_docs/getting-started.md", "markdown", "Getting Started Guide"),
    ("product_docs/integrations.md", "markdown", "Integrations"),
    ("product_docs/user-management.md", "markdown", "User Management"),
    ("faqs/billing-faq.md", "markdown", "Billing FAQ"),
    ("faqs/limits-faq.md", "markdown", "Rate Limits and Storage FAQ"),
    ("troubleshooting/integration-issues.md", "markdown", "Integration Troubleshooting"),
    ("policies/refund-policy.md", "markdown", "Refund Policy"),
    ("release_notes/v3.2-release.md", "markdown", "AcmeSaaS v3.2 Release Notes"),
    ("api_docs/authentication.md", "markdown", "API Authentication"),
]


async def get_or_create_workspace(session: AsyncSession) -> tuple:
    """Get existing workspace or fail with instructions."""
    result = await session.execute(select(Workspace).limit(1))
    workspace = result.scalar_one_or_none()

    if not workspace:
        print("No workspace found. Please register a user first via the API:")
        print("  POST http://localhost:8001/api/v1/auth/register")
        sys.exit(1)

    result = await session.execute(
        select(User).where(User.workspace_id == workspace.id).limit(1)
    )
    user = result.scalar_one_or_none()
    if not user:
        print("No user found in workspace. Register first.")
        sys.exit(1)

    return workspace, user


async def ingest_document(
    session: AsyncSession,
    workspace_id,
    user_id,
    file_path: str,
    source_type: str,
    title: str,
) -> None:
    """Create document record and process it."""
    full_path = SAMPLE_DIR / file_path

    if not full_path.exists():
        print(f"  SKIP {file_path} (file not found)")
        return

    # check if already ingested
    result = await session.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.title == title,
            Document.status == "active",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        print(f"  SKIP {title} (already ingested)")
        return

    file_size = full_path.stat().st_size

    doc = Document(
        workspace_id=workspace_id,
        title=title,
        source_type=source_type,
        file_path=str(full_path),
        file_size_bytes=file_size,
        mime_type="text/markdown",
        status="processing",
        uploaded_by=user_id,
    )
    session.add(doc)
    await session.flush()

    job = IngestionJob(
        workspace_id=workspace_id,
        document_id=doc.id,
        status="processing",
    )
    session.add(job)
    await session.flush()

    print(f"  Processing: {title}...")

    try:
        await process_document(doc.id, session)
        job.status = "completed"
        await session.flush()
        print(f"  OK: {title} (ingested)")
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        doc.status = "failed"
        await session.flush()
        print(f"  FAIL: {title} — {e}")


async def main():
    print("=== TrustRAG Sample Data Seeder ===\n")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        workspace, user = await get_or_create_workspace(session)
        print(f"Workspace: {workspace.name} (id: {workspace.id})")
        print(f"User: {user.name} ({user.email})\n")

        print(f"Ingesting {len(DOCUMENT_SOURCES)} documents...\n")

        for file_path, source_type, title in DOCUMENT_SOURCES:
            await ingest_document(
                session, workspace.id, user.id, file_path, source_type, title
            )

        await session.commit()

    await engine.dispose()
    print("\nDone! You can now query the knowledge base via the chat interface.")


if __name__ == "__main__":
    asyncio.run(main())
