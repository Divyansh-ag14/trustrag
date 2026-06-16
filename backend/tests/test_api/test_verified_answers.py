"""Tests for verified answers — matching service and the approve API."""

from unittest.mock import patch

from app.models.feedback import Feedback
from app.services.verified_answer_service import (
    create_verified_answer,
    match_verified_answer,
)
from tests.conftest import auth_header


class TestMatching:
    @patch("app.services.verified_answer_service.embed_single", return_value=[1.0, 0.0, 0.0])
    async def test_create_then_match(self, _embed, db, workspace):
        va = await create_verified_answer(
            db, workspace.id, "How do I reset my password?", "Go to Settings > Security."
        )
        match = await match_verified_answer(db, workspace.id, "How do I reset my password?")
        assert match is not None
        assert match[0].id == va.id

    async def test_no_verified_answers_returns_none(self, db, workspace):
        # Nothing stored → returns None without any embedding call.
        assert await match_verified_answer(db, workspace.id, "anything") is None

    @patch("app.services.verified_answer_service.embed_single")
    async def test_below_threshold_no_match(self, mock_embed, db, workspace):
        # store vec A, query orthogonal vec B → cosine 0 → no match
        mock_embed.side_effect = [[1.0, 0.0], [0.0, 1.0]]
        await create_verified_answer(db, workspace.id, "Q", "A")
        assert await match_verified_answer(db, workspace.id, "different") is None


class TestApproveAPI:
    @patch("app.services.verified_answer_service.embed_single", return_value=[0.1, 0.2, 0.3])
    async def test_admin_approves_correction(
        self, _embed, client, db, admin_user, sample_query_result
    ):
        fb = Feedback(
            query_result_id=sample_query_result.id,
            user_id=admin_user.id,
            rating="down",
            corrected_answer="Enterprise customers get a full refund within 30 days.",
        )
        db.add(fb)
        await db.flush()

        resp = await client.post(
            f"/api/v1/verified-answers/from-feedback/{fb.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["question"] == "What is the refund policy?"
        assert body["answer"] == "Enterprise customers get a full refund within 30 days."

        # now it lists
        listed = await client.get("/api/v1/verified-answers/", headers=auth_header(admin_user))
        assert len(listed.json()) == 1

    async def test_member_forbidden(self, client, db, member_user, sample_query_result):
        fb = Feedback(query_result_id=sample_query_result.id, rating="down", corrected_answer="x")
        db.add(fb)
        await db.flush()
        resp = await client.post(
            f"/api/v1/verified-answers/from-feedback/{fb.id}",
            headers=auth_header(member_user),
        )
        assert resp.status_code == 403

    async def test_no_corrected_answer_rejected(self, client, db, admin_user, sample_query_result):
        fb = Feedback(query_result_id=sample_query_result.id, rating="down", corrected_answer=None)
        db.add(fb)
        await db.flush()
        resp = await client.post(
            f"/api/v1/verified-answers/from-feedback/{fb.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 400
