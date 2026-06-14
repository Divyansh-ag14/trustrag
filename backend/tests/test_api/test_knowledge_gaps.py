"""Tests for knowledge gaps — recording (with dedup) and the admin API."""

from app.services.knowledge_gap_service import record_knowledge_gap
from tests.conftest import auth_header


class TestRecordGap:
    async def test_creates_open_gap(self, db, workspace):
        gap = await record_knowledge_gap(db, workspace.id, "How do I export data?", "no_answer")
        assert gap.status == "open"
        assert gap.occurrences == 1
        assert gap.reason == "no_answer"

    async def test_dedup_increments_occurrences(self, db, workspace):
        g1 = await record_knowledge_gap(db, workspace.id, "Same question?", "no_answer")
        # Same question (case-insensitive) while still open → bump, don't duplicate.
        g2 = await record_knowledge_gap(db, workspace.id, "same question?", "low_confidence")
        assert g1.id == g2.id
        assert g2.occurrences == 2

    async def test_resolved_gap_not_deduped(self, db, workspace):
        g1 = await record_knowledge_gap(db, workspace.id, "Recurring Q", "no_answer")
        g1.status = "resolved"
        await db.flush()
        g2 = await record_knowledge_gap(db, workspace.id, "Recurring Q", "no_answer")
        assert g1.id != g2.id  # a fresh open gap is created


class TestKnowledgeGapAPI:
    async def test_list_and_stats(self, client, db, workspace, admin_user):
        await record_knowledge_gap(db, workspace.id, "Q1", "no_answer")
        await record_knowledge_gap(db, workspace.id, "Q2", "low_confidence")

        listed = await client.get("/api/v1/knowledge-gaps/", headers=auth_header(admin_user))
        assert listed.status_code == 200
        assert len(listed.json()) == 2

        stats = await client.get("/api/v1/knowledge-gaps/stats", headers=auth_header(admin_user))
        body = stats.json()
        assert body["total"] == 2
        assert body["open"] == 2
        assert body["by_reason"]["no_answer"] == 1

    async def test_filter_by_status(self, client, db, workspace, admin_user):
        g1 = await record_knowledge_gap(db, workspace.id, "Open one", "no_answer")
        g2 = await record_knowledge_gap(db, workspace.id, "Resolved one", "no_answer")
        g2.status = "resolved"
        await db.flush()

        resolved = await client.get(
            "/api/v1/knowledge-gaps/?status=resolved", headers=auth_header(admin_user)
        )
        ids = [g["id"] for g in resolved.json()]
        assert str(g2.id) in ids and str(g1.id) not in ids

    async def test_admin_can_resolve(self, client, db, workspace, admin_user):
        gap = await record_knowledge_gap(db, workspace.id, "Resolve me", "no_answer")
        resp = await client.patch(
            f"/api/v1/knowledge-gaps/{gap.id}",
            json={"status": "resolved", "resolution_notes": "Added a doc"},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"

    async def test_member_cannot_update(self, client, db, workspace, member_user):
        gap = await record_knowledge_gap(db, workspace.id, "Q", "no_answer")
        resp = await client.patch(
            f"/api/v1/knowledge-gaps/{gap.id}",
            json={"status": "resolved"},
            headers=auth_header(member_user),
        )
        assert resp.status_code == 403
