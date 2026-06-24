"""Tests for analytics API — usage, quality, costs, latency."""

from httpx import AsyncClient

from app.models.query import QueryResult
from app.models.user import User
from tests.conftest import auth_header


class TestUsageAnalytics:
    async def test_usage_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/v1/analytics/usage?days=7",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_queries" in data
        assert data["total_queries"] == 0

    async def test_usage_with_data(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.get(
            "/api/v1/analytics/usage?days=7",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_queries"] >= 1


class TestQualityAnalytics:
    async def test_quality_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/v1/analytics/quality?days=7",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    async def test_quality_with_data(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.get(
            "/api/v1/analytics/quality?days=30",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "avg_confidence" in data


class TestCostAnalytics:
    async def test_costs_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/v1/analytics/costs?days=7",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    async def test_costs_with_data(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.get(
            "/api/v1/analytics/costs?days=30",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data


class TestLatencyAnalytics:
    async def test_latency_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/v1/analytics/latency?days=7",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    async def test_latency_with_data(
        self, client: AsyncClient, admin_user: User, sample_query_result: QueryResult,
    ):
        resp = await client.get(
            "/api/v1/analytics/latency?days=30",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data or "p50" in data or "avg_latency_ms" in data
