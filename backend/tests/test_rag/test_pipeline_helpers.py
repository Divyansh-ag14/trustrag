"""Tests for pipeline cost/token helpers."""

from app.rag.pipeline import _aggregate_token_usage


class TestAggregateTokenUsage:
    def test_sums_all_llm_calls(self):
        # generation + query-understanding + citation + hallucination calls
        usage = _aggregate_token_usage((100, 20), (50, 10), (30, 5), (40, 8))
        assert usage == {
            "prompt_tokens": 220,
            "completion_tokens": 43,
            "total_tokens": 263,
        }

    def test_empty(self):
        assert _aggregate_token_usage() == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
