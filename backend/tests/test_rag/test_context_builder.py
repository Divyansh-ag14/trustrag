"""Tests for the RAG context builder — dedup, diversity, budget, conflicts."""

import uuid
from datetime import datetime, timedelta, timezone

from app.rag.context_builder import (
    _deduplicate,
    _detect_conflicts,
    _detect_stale_sources,
    _enforce_diversity,
    _jaccard_similarity,
    build_context,
)
from app.rag.retriever import RetrievedChunk


def _make_chunk(
    content: str = "test content",
    doc_id: uuid.UUID | None = None,
    title: str = "Doc",
    score: float = 0.9,
    updated_at: datetime | None = None,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id or uuid.uuid4(),
        document_title=title,
        content=content,
        source_type="markdown",
        chunk_index=0,
        final_score=score,
        rrf_score=score,
        doc_updated_at=updated_at,
    )


class TestJaccardSimilarity:
    def test_identical(self):
        assert _jaccard_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _jaccard_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        sim = _jaccard_similarity("the quick brown fox", "the slow brown cat")
        assert 0.0 < sim < 1.0

    def test_empty_strings(self):
        assert _jaccard_similarity("", "") == 0.0

    def test_one_empty(self):
        assert _jaccard_similarity("hello", "") == 0.0


class TestDeduplication:
    def test_removes_near_duplicates(self):
        chunks = [
            _make_chunk("the quick brown fox jumps over the lazy dog", score=0.9),
            _make_chunk("the quick brown fox jumps over the lazy dog", score=0.8),
        ]
        result = _deduplicate(chunks, threshold=0.8)
        assert len(result) == 1
        assert result[0].final_score == 0.9  # keeps higher-scored

    def test_keeps_different_chunks(self):
        chunks = [
            _make_chunk("refund policy for enterprise customers", score=0.9),
            _make_chunk("slack integration setup guide steps", score=0.8),
        ]
        result = _deduplicate(chunks, threshold=0.8)
        assert len(result) == 2

    def test_empty_input(self):
        assert _deduplicate([]) == []


class TestEnforceDiversity:
    def test_limits_per_document(self):
        doc_id = uuid.uuid4()
        chunks = [_make_chunk(f"content {i}", doc_id=doc_id) for i in range(5)]
        result = _enforce_diversity(chunks, max_per_doc=3)
        assert len(result) == 3

    def test_different_docs_unaffected(self):
        chunks = [_make_chunk(f"content {i}") for i in range(5)]
        result = _enforce_diversity(chunks, max_per_doc=3)
        assert len(result) == 5  # each has unique doc_id


class TestDetectStale:
    def test_flags_old_sources(self):
        old_date = datetime.now(timezone.utc) - timedelta(days=200)
        chunks = [_make_chunk("content", title="Old Doc", updated_at=old_date)]
        stale = _detect_stale_sources(chunks)
        assert "Old Doc" in stale

    def test_ignores_recent_sources(self):
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        chunks = [_make_chunk("content", updated_at=recent)]
        assert _detect_stale_sources(chunks) == []

    def test_no_date_not_flagged(self):
        chunks = [_make_chunk("content", updated_at=None)]
        assert _detect_stale_sources(chunks) == []


class TestDetectConflicts:
    def test_detects_large_date_gap(self):
        doc1 = uuid.uuid4()
        doc2 = uuid.uuid4()
        now = datetime.now(timezone.utc)
        chunks = [
            _make_chunk("a", doc_id=doc1, updated_at=now),
            _make_chunk("b", doc_id=doc2, updated_at=now - timedelta(days=100)),
        ]
        assert _detect_conflicts(chunks) is True

    def test_no_conflict_same_date(self):
        doc1 = uuid.uuid4()
        doc2 = uuid.uuid4()
        now = datetime.now(timezone.utc)
        chunks = [
            _make_chunk("a", doc_id=doc1, updated_at=now),
            _make_chunk("b", doc_id=doc2, updated_at=now - timedelta(days=10)),
        ]
        assert _detect_conflicts(chunks) is False

    def test_single_chunk_no_conflict(self):
        assert _detect_conflicts([_make_chunk("a")]) is False


class TestBuildContext:
    def test_basic_build(self):
        chunks = [
            _make_chunk("First piece of content.", title="Doc A", score=0.9),
            _make_chunk("Second piece of content.", title="Doc B", score=0.8),
        ]
        result = build_context(chunks, token_budget=4000)
        assert "[1]" in result.formatted_context
        assert "[2]" in result.formatted_context
        assert "Doc A" in result.formatted_context
        assert len(result.chunks_used) == 2
        assert result.total_tokens > 0

    def test_respects_token_budget(self):
        # Create chunks that are big enough to exceed a small budget
        big_chunks = [
            _make_chunk("word " * 100, title=f"Doc {i}", score=0.9 - i * 0.1)
            for i in range(5)
        ]
        result = build_context(big_chunks, token_budget=200)
        assert result.total_tokens <= 250  # some slack for headers
        assert len(result.chunks_used) < 5

    def test_empty_input(self):
        result = build_context([], token_budget=4000)
        assert result.formatted_context == ""
        assert result.chunks_used == []
        assert result.total_tokens == 0

    def test_always_includes_at_least_one(self):
        # Even if single chunk exceeds budget, it should still be included
        big_chunk = _make_chunk("word " * 500, title="Huge Doc", score=0.9)
        result = build_context([big_chunk], token_budget=100)
        assert len(result.chunks_used) == 1
