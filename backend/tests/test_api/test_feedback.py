"""Tests for feedback API — submit, list, review, stats."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.models.query import QueryResult
from app.models.user import User
from tests.conftest import auth_header


class TestSubmitFeedback:
    async def test_submit_thumbs_up(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.post(
            "/api/v1/feedback/",
            headers=auth_header(admin_user),
            json={
                "query_result_id": str(sample_query_result.id),
                "rating": "up",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "up"
        assert data["query_result_id"] == str(sample_query_result.id)

    async def test_submit_thumbs_down_with_comment(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.post(
            "/api/v1/feedback/",
            headers=auth_header(admin_user),
            json={
                "query_result_id": str(sample_query_result.id),
                "rating": "down",
                "comment": "Answer was incorrect",
                "corrected_answer": "The actual policy is 60 days.",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rating"] == "down"
        assert data["comment"] == "Answer was incorrect"

    async def test_submit_for_nonexistent_result(
        self, client: AsyncClient, admin_user: User,
    ):
        resp = await client.post(
            "/api/v1/feedback/",
            headers=auth_header(admin_user),
            json={
                "query_result_id": str(uuid.uuid4()),
                "rating": "up",
            },
        )
        assert resp.status_code == 404


class TestListFeedback:
    async def test_list_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/feedback/", headers=auth_header(admin_user))
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_data(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user: User,
        sample_query_result: QueryResult,
    ):
        fb = Feedback(
            query_result_id=sample_query_result.id,
            user_id=admin_user.id,
            rating="up",
        )
        db.add(fb)
        await db.flush()

        resp = await client.get("/api/v1/feedback/", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["rating"] == "up"

    async def test_filter_by_rating(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user: User,
        sample_query_result: QueryResult,
    ):
        fb = Feedback(
            query_result_id=sample_query_result.id,
            user_id=admin_user.id,
            rating="down",
        )
        db.add(fb)
        await db.flush()

        resp = await client.get(
            "/api/v1/feedback/?rating=up",
            headers=auth_header(admin_user),
        )
        assert len(resp.json()) == 0

        resp = await client.get(
            "/api/v1/feedback/?rating=down",
            headers=auth_header(admin_user),
        )
        assert len(resp.json()) == 1


class TestReviewFeedback:
    async def test_review(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user: User,
        sample_query_result: QueryResult,
    ):
        fb = Feedback(
            query_result_id=sample_query_result.id,
            user_id=admin_user.id,
            rating="down",
            comment="bad answer",
        )
        db.add(fb)
        await db.flush()

        resp = await client.patch(
            f"/api/v1/feedback/{fb.id}/review",
            headers=auth_header(admin_user),
            json={"review_note": "Acknowledged, will fix prompt."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_note"] == "Acknowledged, will fix prompt."
        assert data["reviewed_at"] is not None

    async def test_review_nonexistent(self, client: AsyncClient, admin_user: User):
        resp = await client.patch(
            f"/api/v1/feedback/{uuid.uuid4()}/review",
            headers=auth_header(admin_user),
            json={"review_note": "test"},
        )
        assert resp.status_code == 404


class TestFeedbackStats:
    async def test_stats_returns_counts(self, client: AsyncClient, admin_user: User):
        resp = await client.get("/api/v1/feedback/stats", headers=auth_header(admin_user))
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "positive" in data
        assert "negative" in data
        assert "reviewed" in data
        assert "unreviewed" in data
        assert isinstance(data["total"], int)
