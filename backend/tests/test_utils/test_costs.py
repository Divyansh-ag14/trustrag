"""Tests for cost calculation utilities."""

from app.utils.costs import (
    calculate_embedding_cost,
    calculate_llm_cost,
    calculate_rerank_cost,
)


class TestEmbeddingCost:
    def test_zero_tokens(self):
        assert calculate_embedding_cost(0) == 0.0

    def test_1000_tokens(self):
        cost = calculate_embedding_cost(1000)
        assert cost == 0.00002  # $0.02 per 1M tokens

    def test_large_batch(self):
        cost = calculate_embedding_cost(1_000_000)
        assert abs(cost - 0.02) < 0.001

    def test_unknown_model_returns_zero(self):
        cost = calculate_embedding_cost(1000, model="unknown-model")
        assert cost == 0.0


class TestLLMCost:
    def test_gpt4o_cost(self):
        cost = calculate_llm_cost(1000, 500, model="gpt-4o")
        input_cost = (1000 / 1000) * 0.0025
        output_cost = (500 / 1000) * 0.01
        assert abs(cost - (input_cost + output_cost)) < 1e-8

    def test_gpt4o_mini_cost(self):
        cost = calculate_llm_cost(1000, 500, model="gpt-4o-mini")
        input_cost = (1000 / 1000) * 0.00015
        output_cost = (500 / 1000) * 0.0006
        assert abs(cost - (input_cost + output_cost)) < 1e-8

    def test_zero_tokens(self):
        assert calculate_llm_cost(0, 0) == 0.0

    def test_unknown_model_returns_zero(self):
        cost = calculate_llm_cost(1000, 500, model="nonexistent")
        assert cost == 0.0


class TestRerankCost:
    def test_zero_searches(self):
        assert calculate_rerank_cost(0) == 0.0

    def test_one_search_is_default(self):
        # One query = one rerank search (not per document).
        assert abs(calculate_rerank_cost() - 0.001) < 1e-8
        assert abs(calculate_rerank_cost(1) - 0.001) < 1e-8

    def test_multiple_searches(self):
        assert abs(calculate_rerank_cost(1000) - 1.0) < 1e-8
