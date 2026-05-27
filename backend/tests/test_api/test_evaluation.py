"""Tests for evaluation API — datasets, items, runs."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvaluationDataset, EvaluationItem
from app.models.user import User
from tests.conftest import auth_header


class TestDatasets:
    async def test_create_dataset(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/v1/evaluation/datasets",
            headers=auth_header(admin_user),
            json={"name": "My Golden Set", "description": "Test dataset"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Golden Set"
        assert data["item_count"] == 0

    async def test_list_datasets(
        self, client: AsyncClient, admin_user: User, eval_dataset: EvaluationDataset,
    ):
        resp = await client.get(
            "/api/v1/evaluation/datasets",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(d["name"] == "Golden Set" for d in data)

    async def test_get_dataset(
        self, client: AsyncClient, admin_user: User, eval_dataset: EvaluationDataset,
    ):
        resp = await client.get(
            f"/api/v1/evaluation/datasets/{eval_dataset.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Golden Set"

    async def test_get_nonexistent_dataset(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            f"/api/v1/evaluation/datasets/{uuid.uuid4()}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404

    async def test_delete_dataset(
        self, client: AsyncClient, admin_user: User, eval_dataset: EvaluationDataset,
    ):
        resp = await client.delete(
            f"/api/v1/evaluation/datasets/{eval_dataset.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 204

        # Verify it's gone
        resp = await client.get(
            f"/api/v1/evaluation/datasets/{eval_dataset.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


class TestItems:
    async def test_add_items(
        self, client: AsyncClient, admin_user: User, eval_dataset: EvaluationDataset,
    ):
        items = [
            {
                "question": "What is the refund policy?",
                "expected_answer": "30-day refund for enterprise.",
                "expected_source_docs": ["refund-policy.md"],
                "query_type": "factual",
                "difficulty": "easy",
                "tags": ["policy"],
            },
            {
                "question": "How do I set up SSO?",
                "expected_answer": "Go to Settings > SSO.",
                "expected_source_docs": ["sso-setup.md"],
                "query_type": "procedural",
                "difficulty": "medium",
                "tags": ["sso"],
            },
        ]
        resp = await client.post(
            f"/api/v1/evaluation/datasets/{eval_dataset.id}/items",
            headers=auth_header(admin_user),
            json=items,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 2
        assert data[0]["question"] == "What is the refund policy?"

    async def test_list_items(
        self,
        client: AsyncClient,
        db: AsyncSession,
        admin_user: User,
        eval_dataset: EvaluationDataset,
    ):
        item = EvaluationItem(
            dataset_id=eval_dataset.id,
            question="Test question?",
            expected_answer="Test answer.",
            expected_source_docs=[],
        )
        db.add(item)
        await db.flush()

        resp = await client.get(
            f"/api/v1/evaluation/datasets/{eval_dataset.id}/items",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestRuns:
    async def test_trigger_run_on_empty_dataset_fails(
        self, client: AsyncClient, admin_user: User, eval_dataset: EvaluationDataset,
    ):
        resp = await client.post(
            "/api/v1/evaluation/runs",
            headers=auth_header(admin_user),
            json={"dataset_id": str(eval_dataset.id)},
        )
        assert resp.status_code == 400
        assert "no evaluation items" in resp.json()["detail"].lower()

    async def test_list_runs_empty(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/v1/evaluation/runs",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_nonexistent_run(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            f"/api/v1/evaluation/runs/{uuid.uuid4()}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404
