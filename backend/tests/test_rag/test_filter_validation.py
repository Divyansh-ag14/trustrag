"""Tests for _validate_filters — the source-type filter gating.

Regression target: query understanding tends to emit a spurious source_types
filter (listing the common sample-data types), which silently excluded
connector-sourced docs (notion/github/web) from retrieval. The filter must only
be honored when the query actually references a source.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.rag.pipeline import _validate_filters


async def _add_doc(db: AsyncSession, workspace: Workspace, admin_user: User, source_type: str):
    doc = Document(
        workspace_id=workspace.id,
        title=f"{source_type} doc",
        source_type=source_type,
        status="active",
        uploaded_by=admin_user.id,
        total_chunks=1,
    )
    db.add(doc)
    await db.flush()
    return doc


class TestFilterGating:
    async def test_none_filters_passthrough(self, db, workspace):
        assert await _validate_filters(db, workspace.id, None) is None

    async def test_no_source_types_passthrough(self, db, workspace):
        f = {"date_range": {"after": "2025-01-01"}}
        assert await _validate_filters(db, workspace.id, f, query_text="anything") == f

    async def test_spurious_filter_dropped_when_query_has_no_source_keyword(self, db, workspace):
        # The bug: a general question with no source reference must NOT carry a
        # source_types filter (which would exclude connector docs).
        f = {"source_types": ["markdown", "faq"], "date_range": {}}
        out = await _validate_filters(
            db, workspace.id, f, query_text="how many users does the Pro plan support?"
        )
        assert "source_types" not in out
        assert out["date_range"] == {}  # other keys preserved

    async def test_filter_honored_when_query_references_source(self, db, workspace, admin_user):
        await _add_doc(db, workspace, admin_user, "notion")
        f = {"source_types": ["notion"]}
        out = await _validate_filters(
            db, workspace.id, f, query_text="what does our Notion page say?"
        )
        assert out["source_types"] == ["notion"]

    async def test_referenced_but_type_absent_in_workspace_drops_to_none(self, db, workspace):
        # Query references slack, but no slack docs exist → nothing to filter on.
        f = {"source_types": ["slack_export"]}
        out = await _validate_filters(
            db, workspace.id, f, query_text="what was said in Slack about billing?"
        )
        assert out is None

    async def test_referenced_keeps_only_existing_types(self, db, workspace, admin_user):
        await _add_doc(db, workspace, admin_user, "github")
        # Query mentions both github and notion, but only github docs exist.
        f = {"source_types": ["github", "notion"]}
        out = await _validate_filters(
            db, workspace.id, f, query_text="check the github repo and notion",
        )
        assert out["source_types"] == ["github"]
