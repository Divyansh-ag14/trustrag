"""Tests for health check endpoints."""

import pytest
from httpx import AsyncClient


class TestHealth:
    async def test_liveness(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    async def test_readiness(self, client: AsyncClient):
        resp = await client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "checks" in data
        assert data["checks"]["postgres"] == "ok"
