COST_PER_1K_TOKENS = {
    "text-embedding-3-small": {"input": 0.00002},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}

# Cohere charges per rerank SEARCH (one call, regardless of doc count), not per
# document. One query = one search. ~$1 per 1,000 searches.
COHERE_RERANK_COST_PER_SEARCH = 0.001


def calculate_embedding_cost(token_count: int, model: str = "text-embedding-3-small") -> float:
    rate = COST_PER_1K_TOKENS.get(model, {}).get("input", 0)
    return (token_count / 1000) * rate


def calculate_llm_cost(
    prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o"
) -> float:
    rates = COST_PER_1K_TOKENS.get(model, {"input": 0, "output": 0})
    input_cost = (prompt_tokens / 1000) * rates.get("input", 0)
    output_cost = (completion_tokens / 1000) * rates.get("output", 0)
    return input_cost + output_cost


def calculate_rerank_cost(num_searches: int = 1) -> float:
    """Cost of rerank searches. One query = one search (not per document)."""
    return num_searches * COHERE_RERANK_COST_PER_SEARCH
