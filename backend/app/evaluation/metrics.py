"""Retrieval and generation quality metrics for evaluation runs."""

import json
import math
from dataclasses import dataclass

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def recall_at_k(retrieved_doc_ids: list[str], expected_doc_ids: list[str], k: int = 10) -> float:
    """Fraction of expected documents found in the top-k retrieved results.

    recall@k = |expected ∩ retrieved[:k]| / |expected|
    """
    if not expected_doc_ids:
        return 1.0

    retrieved_set = set(retrieved_doc_ids[:k])
    expected_set = set(expected_doc_ids)
    hits = retrieved_set & expected_set
    return len(hits) / len(expected_set)


def precision_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 10) -> float:
    """Fraction of top-k retrieved documents that are relevant.

    precision@k = |relevant ∩ retrieved[:k]| / k
    """
    if k == 0:
        return 0.0

    retrieved_set = set(retrieved_doc_ids[:k])
    relevant_set = set(relevant_doc_ids)
    hits = retrieved_set & relevant_set
    return len(hits) / k


def mrr(retrieved_doc_ids: list[str], relevant_doc_ids: list[str]) -> float:
    """Mean Reciprocal Rank — 1/rank of the first relevant document.

    MRR = 1 / rank_of_first_relevant
    Returns 0 if no relevant document is found.
    """
    relevant_set = set(relevant_doc_ids)

    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: list[str], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain at k.

    Uses binary relevance: 1 if document is in relevant set, 0 otherwise.
    NDCG@k = DCG@k / IDCG@k
    """
    relevant_set = set(relevant_doc_ids)

    # DCG: sum of relevance / log2(rank + 1) for top-k
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_doc_ids[:k]):
        if doc_id in relevant_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because rank starts at 1, log2(1+1)

    # IDCG: best possible DCG with |relevant| items at top
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    if idcg == 0:
        return 0.0

    return dcg / idcg


def hit_rate(retrieved_doc_ids: list[str], expected_doc_ids: list[str], k: int = 10) -> float:
    """Binary: 1 if any expected document appears in top-k, else 0."""
    retrieved_set = set(retrieved_doc_ids[:k])
    expected_set = set(expected_doc_ids)
    return 1.0 if retrieved_set & expected_set else 0.0


def average_precision(retrieved_doc_ids: list[str], relevant_doc_ids: list[str]) -> float:
    """Average Precision for a single query.

    AP = (1/|relevant|) * sum(precision@k * rel(k)) for k=1..n
    """
    relevant_set = set(relevant_doc_ids)
    if not relevant_set:
        return 1.0

    hits = 0
    sum_precision = 0.0

    for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant_set:
            hits += 1
            sum_precision += hits / rank

    if hits == 0:
        return 0.0

    return sum_precision / len(relevant_set)


# --- Generation quality: answer relevance (LLM judge) -----------------------

ANSWER_RELEVANCE_SYSTEM = """You score how well an ANSWER addresses a QUESTION — relevance only, NOT factual correctness.

Score 0.0 to 1.0:
- 1.0: directly and completely addresses what was asked
- 0.5: partially addresses it, or answers a related but different question
- 0.0: does not address the question, is evasive, or is a refusal/"I don't know"

Return ONLY JSON: {"score": <float 0.0-1.0>}"""


@dataclass
class AnswerRelevanceResult:
    score: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


def answer_relevance(question: str, answer: str) -> AnswerRelevanceResult:
    """LLM-judge: how directly does the answer address the question? (0.0–1.0)."""
    if not answer.strip():
        return AnswerRelevanceResult(score=0.0)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": ANSWER_RELEVANCE_SYSTEM},
                {"role": "user", "content": json.dumps({"question": question, "answer": answer[:4000]})},
            ],
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "{}").strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]
        score = float(json.loads(content.strip()).get("score", 0.0))
        usage = response.usage
        return AnswerRelevanceResult(
            score=max(0.0, min(1.0, score)),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
    except Exception:
        return AnswerRelevanceResult(score=0.0)
