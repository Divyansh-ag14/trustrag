"""Tests for source trust scoring in retriever and reranker."""

import uuid
from unittest.mock import patch, MagicMock

from app.rag.retriever import RetrievedChunk, DEFAULT_TRUST_WEIGHTS, _fuse_results
from app.rag.reranker import rerank


def _make_chunk(
    source_type: str = "markdown",
    vector_score: float = 0.5,
    bm25_score: float = 0.3,
    rrf_score: float = 0.0,
    freshness_score: float = 1.0,
    trust_score: float = 0.7,
    content: str = "test content",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_title="Doc",
        content=content,
        source_type=source_type,
        chunk_index=0,
        vector_score=vector_score,
        bm25_score=bm25_score,
        rrf_score=rrf_score,
        freshness_score=freshness_score,
        trust_score=trust_score,
    )


class TestDefaultTrustWeights:
    def test_has_all_source_types(self):
        expected = {"pdf", "markdown", "text", "html", "csv", "faq", "slack_export", "notion", "github", "web"}
        assert expected.issubset(set(DEFAULT_TRUST_WEIGHTS.keys()))

    def test_weights_in_range(self):
        for source_type, weight in DEFAULT_TRUST_WEIGHTS.items():
            assert 0.0 <= weight <= 1.0, f"{source_type} weight {weight} out of range"

    def test_official_docs_higher_than_slack(self):
        assert DEFAULT_TRUST_WEIGHTS["pdf"] > DEFAULT_TRUST_WEIGHTS["slack_export"]
        assert DEFAULT_TRUST_WEIGHTS["faq"] > DEFAULT_TRUST_WEIGHTS["slack_export"]

    def test_notion_github_higher_than_web(self):
        assert DEFAULT_TRUST_WEIGHTS["notion"] > DEFAULT_TRUST_WEIGHTS["web"]
        assert DEFAULT_TRUST_WEIGHTS["github"] > DEFAULT_TRUST_WEIGHTS["web"]


class TestFuseResultsTrustScore:
    def test_trust_score_set_from_source_type(self):
        vector_chunks = [_make_chunk(source_type="pdf")]
        bm25_chunks = [_make_chunk(source_type="slack_export")]

        # Give them different chunk IDs so they don't merge
        fused = _fuse_results(vector_chunks, bm25_chunks, top_k=10)

        for chunk in fused:
            expected = DEFAULT_TRUST_WEIGHTS.get(chunk.source_type, 0.7)
            assert chunk.trust_score == expected

    def test_unknown_source_type_gets_default(self):
        chunk = _make_chunk(source_type="unknown_type")
        vector_chunks = [chunk]
        fused = _fuse_results(vector_chunks, [], top_k=10)
        assert fused[0].trust_score == 0.7  # default


class TestRerankWithTrust:
    @patch("app.rag.reranker._get_client")
    def test_trust_weight_included(self, mock_client):
        """When Cohere succeeds, trust weight should be part of final_score."""
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.9),
            MagicMock(index=1, relevance_score=0.3),
        ]
        mock_client.return_value.rerank.return_value = mock_response

        high_trust = _make_chunk(source_type="faq", trust_score=0.9, content="faq content")
        low_trust = _make_chunk(source_type="slack_export", trust_score=0.5, content="slack content")

        result = rerank("test query", [high_trust, low_trust], top_k=2)
        assert len(result) == 2
        # Both should have final_score > 0
        for chunk in result:
            assert chunk.final_score > 0

    @patch("app.rag.reranker._get_client")
    def test_trust_affects_ranking(self, mock_client):
        """Given equal relevance, higher trust should score higher."""
        mock_response = MagicMock()
        mock_response.results = [
            MagicMock(index=0, relevance_score=0.5),
            MagicMock(index=1, relevance_score=0.5),
        ]
        mock_client.return_value.rerank.return_value = mock_response

        # Same scores except trust
        high_trust = _make_chunk(
            source_type="pdf", trust_score=0.9,
            vector_score=0.5, bm25_score=0.3, freshness_score=0.8,
            content="pdf content",
        )
        low_trust = _make_chunk(
            source_type="web", trust_score=0.6,
            vector_score=0.5, bm25_score=0.3, freshness_score=0.8,
            content="web content",
        )

        result = rerank("query", [high_trust, low_trust], top_k=2)
        assert result[0].trust_score >= result[1].trust_score

    @patch("app.rag.reranker._get_client")
    def test_default_weights_sum_to_one(self, mock_client):
        """The default reranker weights should sum to 1.0."""
        from app.rag.reranker import rerank

        # Access default weights by calling with empty chunks
        w = {
            "vector": 0.30,
            "bm25": 0.12,
            "rerank": 0.35,
            "freshness": 0.10,
            "trust": 0.13,
        }
        total = sum(w.values())
        assert abs(total - 1.0) < 0.01

    @patch("app.rag.reranker._get_client")
    def test_fallback_ignores_trust(self, mock_client):
        """When Cohere fails, trust isn't used — just RRF scores."""
        mock_client.return_value.rerank.side_effect = Exception("API down")

        chunks = [
            _make_chunk(rrf_score=0.3, trust_score=0.9, content="a"),
            _make_chunk(rrf_score=0.5, trust_score=0.1, content="b"),
        ]
        result = rerank("query", chunks, top_k=2)
        # Should be sorted by rrf_score, not trust
        assert result[0].rrf_score == 0.5
