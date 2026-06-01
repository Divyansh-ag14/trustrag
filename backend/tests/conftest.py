"""Shared fixtures for all tests.

Uses the LIVE PostgreSQL database (port 5435). Each test gets a fresh
engine + connection + transaction. The transaction is rolled back after
the test so nothing persists.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import settings

# Increase rate limit for tests before app is imported
settings.RATE_LIMIT_PER_MINUTE = 100000

from app.database import get_db
from app.main import app

from app.models.workspace import Workspace
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.models.query import Query, QueryResult
from app.models.evaluation import EvaluationDataset
from app.services.auth_service import create_access_token, hash_password


# ---------------------------------------------------------------------------
# Core DB fixture — per-test engine avoids cross-loop issues
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session; rollback everything after the test."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.connect() as conn:
        txn = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            if txn.is_active:
                await txn.rollback()

    await engine.dispose()


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired to the test DB session.

    Monkey-patches commit → flush so route commits don't end the
    test transaction.
    """
    _real_commit = db.commit

    async def _fake_commit():
        await db.flush()

    db.commit = _fake_commit  # type: ignore[assignment]

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    db.commit = _real_commit  # type: ignore[assignment]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Data factory fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def workspace(db: AsyncSession) -> Workspace:
    ws = Workspace(name="Test Workspace", slug=f"test-{uuid.uuid4().hex[:8]}", settings={})
    db.add(ws)
    await db.flush()
    return ws


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession, workspace: Workspace) -> User:
    user = User(
        workspace_id=workspace.id,
        email=f"admin-{uuid.uuid4().hex[:6]}@test.com",
        name="Test Admin",
        role="admin",
        hashed_password=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def member_user(db: AsyncSession, workspace: Workspace) -> User:
    user = User(
        workspace_id=workspace.id,
        email=f"member-{uuid.uuid4().hex[:6]}@test.com",
        name="Test Member",
        role="member",
        hashed_password=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession, workspace: Workspace) -> User:
    user = User(
        workspace_id=workspace.id,
        email=f"viewer-{uuid.uuid4().hex[:6]}@test.com",
        name="Test Viewer",
        role="viewer",
        hashed_password=hash_password("testpass123"),
    )
    db.add(user)
    await db.flush()
    return user


def auth_header(user: User) -> dict[str, str]:
    """Build an Authorization header from a user fixture."""
    token = create_access_token(user.id, user.workspace_id)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_document(db: AsyncSession, workspace: Workspace, admin_user: User) -> Document:
    doc = Document(
        workspace_id=workspace.id,
        title="Test Document",
        source_type="markdown",
        status="active",
        uploaded_by=admin_user.id,
        total_chunks=2,
    )
    db.add(doc)
    await db.flush()
    return doc


@pytest_asyncio.fixture
async def sample_chunks(db: AsyncSession, sample_document: Document) -> list[DocumentChunk]:
    chunks = []
    for i, text in enumerate([
        "AcmeSaaS offers enterprise refund policy. Enterprise customers can request a full refund within 30 days.",
        "To set up Slack integration, go to Settings > Integrations > Slack and click Connect.",
    ]):
        chunk = DocumentChunk(
            document_id=sample_document.id,
            chunk_index=i,
            content=text,
            token_count=20,
            embedding_id=f"emb_{uuid.uuid4().hex[:8]}",
            metadata_={},
        )
        db.add(chunk)
        chunks.append(chunk)
    await db.flush()
    return chunks


@pytest_asyncio.fixture
async def sample_query_result(
    db: AsyncSession, workspace: Workspace, admin_user: User,
) -> QueryResult:
    query = Query(
        workspace_id=workspace.id,
        user_id=admin_user.id,
        original_query="What is the refund policy?",
        session_id=uuid.uuid4(),
    )
    db.add(query)
    await db.flush()

    result = QueryResult(
        query_id=query.id,
        answer="Enterprise customers can request a full refund within 30 days.",
        confidence_score=0.9,
        faithfulness_score=1.0,
        hallucination_score=0.0,
        citation_accuracy=1.0,
        latency_ms=5000,
        latency_breakdown={
            "query_understanding_ms": 500,
            "retrieval_ms": 300,
            "rerank_ms": 200,
            "context_build_ms": 10,
            "generation_ms": 3000,
            "citation_validation_ms": 500,
            "hallucination_check_ms": 490,
            "total_ms": 5000,
        },
        token_usage={"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600},
        cost_usd=0.005,
        citations=[{
            "index": 1,
            "document_title": "Refund Policy",
            "chunk_snippet": "...",
            "document_id": str(uuid.uuid4()),
            "relevance_score": 0.95,
        }],
        status="success",
        retrieval_trace={"query_type": "factual", "intent": "lookup"},
    )
    db.add(result)
    await db.flush()
    return result


@pytest_asyncio.fixture
async def eval_dataset(db: AsyncSession, workspace: Workspace) -> EvaluationDataset:
    ds = EvaluationDataset(
        workspace_id=workspace.id,
        name="Golden Set",
        description="Test eval dataset",
        item_count=0,
    )
    db.add(ds)
    await db.flush()
    return ds


# ---------------------------------------------------------------------------
# Simple helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_text():
    return """# Getting Started with AcmeSaaS

AcmeSaaS is a B2B project management tool designed for teams of all sizes.

## Quick Setup

1. Create your workspace at app.acmesaas.com
2. Invite your team members via Settings > Users
3. Create your first project using a template or from scratch

## Key Features

AcmeSaaS offers task management, reporting, integrations, and API access.
Each feature is designed to help teams collaborate more effectively.

## Support

For help, contact support@acmesaas.com or visit our help center.
"""
