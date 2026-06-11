"""Regression detection — compare an evaluation run against recent history.

Flags any metric that degraded by more than a threshold (absolute) versus the
average of the last N runs, so a prompt/retrieval change that quietly hurts
quality is caught before it ships.
"""

# (metric_key, higher_is_better)
REGRESSION_METRICS: list[tuple[str, bool]] = [
    ("recall_at_10", True),
    ("precision_at_10", True),
    ("mrr", True),
    ("ndcg_at_10", True),
    ("faithfulness", True),
    ("citation_accuracy", True),
    ("answer_relevance", True),
    ("avg_confidence", True),
    ("hallucination_rate", False),  # lower is better
]

DEFAULT_THRESHOLD = 0.05  # 5% absolute
DEFAULT_BASELINE_RUNS = 3


def detect_regressions(
    current: dict,
    history: list[dict],
    threshold: float = DEFAULT_THRESHOLD,
    baseline_runs: int = DEFAULT_BASELINE_RUNS,
) -> list[dict]:
    """Return metrics that degraded > threshold vs the average of recent runs.

    Args:
        current: metrics dict of the run being evaluated.
        history: prior runs' metrics dicts, MOST RECENT FIRST.
        threshold: absolute degradation that counts as a regression.
        baseline_runs: how many recent runs to average for the baseline.
    """
    if not history:
        return []

    baseline_set = history[:baseline_runs]
    regressions = []

    for key, higher_is_better in REGRESSION_METRICS:
        cur = current.get(key)
        prior = [h[key] for h in baseline_set if isinstance(h.get(key), (int, float))]
        if not isinstance(cur, (int, float)) or not prior:
            continue

        baseline = sum(prior) / len(prior)
        # degraded_by is positive when the metric got worse
        degraded_by = (baseline - cur) if higher_is_better else (cur - baseline)

        if degraded_by > threshold:
            regressions.append({
                "metric": key,
                "current": round(cur, 4),
                "baseline": round(baseline, 4),
                "degraded_by": round(degraded_by, 4),
            })

    return regressions
