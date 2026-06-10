"""Tests for retrieval quality metrics."""

import math

from app.evaluation.metrics import (
    average_precision,
    hit_rate,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


class TestRecallAtK:
    def test_perfect_recall(self):
        retrieved = ["a", "b", "c"]
        expected = ["a", "b"]
        assert recall_at_k(retrieved, expected, k=3) == 1.0

    def test_partial_recall(self):
        retrieved = ["a", "b", "c"]
        expected = ["a", "d"]
        assert recall_at_k(retrieved, expected, k=3) == 0.5

    def test_zero_recall(self):
        retrieved = ["a", "b", "c"]
        expected = ["d", "e"]
        assert recall_at_k(retrieved, expected, k=3) == 0.0

    def test_k_limits_retrieved(self):
        retrieved = ["a", "b", "c", "d"]
        expected = ["d"]
        assert recall_at_k(retrieved, expected, k=2) == 0.0
        assert recall_at_k(retrieved, expected, k=4) == 1.0

    def test_empty_expected_returns_one(self):
        assert recall_at_k(["a", "b"], [], k=5) == 1.0

    def test_empty_retrieved(self):
        assert recall_at_k([], ["a"], k=5) == 0.0


class TestPrecisionAtK:
    def test_perfect_precision(self):
        retrieved = ["a", "b"]
        relevant = ["a", "b", "c"]
        assert precision_at_k(retrieved, relevant, k=2) == 1.0

    def test_half_precision(self):
        retrieved = ["a", "x"]
        relevant = ["a", "b"]
        assert precision_at_k(retrieved, relevant, k=2) == 0.5

    def test_zero_precision(self):
        retrieved = ["x", "y", "z"]
        relevant = ["a", "b"]
        assert precision_at_k(retrieved, relevant, k=3) == 0.0

    def test_k_zero_returns_zero(self):
        assert precision_at_k(["a"], ["a"], k=0) == 0.0


class TestMRR:
    def test_first_position(self):
        assert mrr(["a", "b", "c"], ["a"]) == 1.0

    def test_second_position(self):
        assert mrr(["x", "a", "b"], ["a"]) == 0.5

    def test_third_position(self):
        assert abs(mrr(["x", "y", "a"], ["a"]) - 1 / 3) < 1e-9

    def test_no_relevant(self):
        assert mrr(["x", "y", "z"], ["a"]) == 0.0

    def test_multiple_relevant_returns_first(self):
        assert mrr(["x", "a", "b"], ["a", "b"]) == 0.5


class TestNDCG:
    def test_perfect_ranking(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b"]
        score = ndcg_at_k(retrieved, relevant, k=3)
        assert score == 1.0

    def test_reversed_ranking(self):
        retrieved = ["x", "y", "a", "b"]
        relevant = ["a", "b"]
        score = ndcg_at_k(retrieved, relevant, k=4)
        assert 0 < score < 1.0

    def test_no_relevant_returns_zero(self):
        assert ndcg_at_k(["x", "y"], ["a"], k=2) == 0.0

    def test_empty_relevant(self):
        assert ndcg_at_k(["a", "b"], [], k=2) == 0.0

    def test_single_relevant_at_top(self):
        score = ndcg_at_k(["a", "x", "y"], ["a"], k=3)
        assert score == 1.0


class TestHitRate:
    def test_hit(self):
        assert hit_rate(["a", "b", "c"], ["b"], k=3) == 1.0

    def test_miss(self):
        assert hit_rate(["a", "b", "c"], ["d"], k=3) == 0.0

    def test_k_limits(self):
        assert hit_rate(["a", "b", "c", "d"], ["d"], k=2) == 0.0
        assert hit_rate(["a", "b", "c", "d"], ["d"], k=4) == 1.0


class TestAveragePrecision:
    def test_perfect_ranking(self):
        retrieved = ["a", "b", "c"]
        relevant = ["a", "b", "c"]
        ap = average_precision(retrieved, relevant)
        assert abs(ap - 1.0) < 1e-9

    def test_all_at_end(self):
        retrieved = ["x", "y", "a", "b"]
        relevant = ["a", "b"]
        ap = average_precision(retrieved, relevant)
        # p@3 * 1 + p@4 * 1 / 2 = (1/3 + 2/4) / 2
        expected = (1 / 3 + 2 / 4) / 2
        assert abs(ap - expected) < 1e-9

    def test_no_hits(self):
        assert average_precision(["x", "y"], ["a", "b"]) == 0.0

    def test_empty_relevant(self):
        assert average_precision(["a", "b"], []) == 1.0


# --- Answer relevance (LLM judge) ------------------------------------------

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.evaluation.metrics import answer_relevance


def _client_returning(score):
    message = SimpleNamespace(content=json.dumps({"score": score}))
    usage = SimpleNamespace(prompt_tokens=40, completion_tokens=5)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)
    create = lambda **kwargs: response  # noqa: E731
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestAnswerRelevance:
    @patch("app.evaluation.metrics._get_client")
    def test_returns_score_and_tokens(self, mock_get_client):
        mock_get_client.return_value = _client_returning(0.9)
        r = answer_relevance("What is the refund window?", "Enterprise refunds within 30 days.")
        assert r.score == 0.9
        assert r.prompt_tokens == 40

    @patch("app.evaluation.metrics._get_client")
    def test_clamps_out_of_range(self, mock_get_client):
        mock_get_client.return_value = _client_returning(1.7)
        assert answer_relevance("q", "a long enough answer") .score == 1.0

    def test_empty_answer_is_zero(self):
        assert answer_relevance("q", "   ").score == 0.0

    @patch("app.evaluation.metrics._get_client")
    def test_fails_to_zero_on_error(self, mock_get_client):
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("api down")
        assert answer_relevance("q", "some answer text").score == 0.0
