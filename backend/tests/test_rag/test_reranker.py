"""Tests for the reranker — score normalization and RRF fallback."""

import uuid
from unittest.mock import patch

from app.rag.reranker import _normalize, rerank
from app.rag.retriever import RetrievedChunk


def _make_chunk(
    content: str = "test",
    vector_score: float = 0.5,
    bm25_score: float = 0.3,
    rrf_score: float = 0.1,
    freshness_score: float = 1.0,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Doc",
        content=content,
        source_type="markdown",
        chunk_index=0,
        vector_score=vector_score,
        bm25_score=bm25_score,
        rrf_score=rrf_score,
        freshness_score=freshness_score,
    )


class TestNormalize:
    def test_basic(self):
        result = _normalize([1.0, 2.0, 3.0])
        assert result == [0.0, 0.5, 1.0]

    def test_all_same(self):
        result = _normalize([5.0, 5.0, 5.0])
        assert result == [0.5, 0.5, 0.5]

    def test_empty(self):
        assert _normalize([]) == []

    def test_single_value(self):
        result = _normalize([7.0])
        assert result == [0.5]

    def test_two_values(self):
        result = _normalize([0.0, 1.0])
        assert result == [0.0, 1.0]


class TestRerankFallback:
    """When Cohere fails, rerank should fall back to RRF scores."""

    @patch("app.rag.reranker._get_client")
    def test_fallback_uses_rrf_scores(self, mock_client):
        mock_client.return_value.rerank.side_effect = Exception("API down")

        chunks = [
            _make_chunk("a", rrf_score=0.3),
            _make_chunk("b", rrf_score=0.5),
            _make_chunk("c", rrf_score=0.1),
        ]
        result = rerank("test query", chunks, top_k=3)

        # Should be sorted by rrf_score descending
        assert result[0].rrf_score == 0.5
        assert result[1].rrf_score == 0.3
        assert result[2].rrf_score == 0.1

    @patch("app.rag.reranker._get_client")
    def test_fallback_respects_top_k(self, mock_client):
        mock_client.return_value.rerank.side_effect = Exception("API down")

        chunks = [_make_chunk(f"chunk {i}", rrf_score=i * 0.1) for i in range(10)]
        result = rerank("query", chunks, top_k=3)
        assert len(result) == 3

    def test_empty_input(self):
        result = rerank("query", [], top_k=10)
        assert result == []
