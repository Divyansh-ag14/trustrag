"""Retrieval and generation quality metrics for evaluation runs."""

import math


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
