"""Tests for evaluation regression detection."""

from app.evaluation.regression import detect_regressions


class TestDetectRegressions:
    def test_no_history_no_regressions(self):
        assert detect_regressions({"recall_at_10": 0.5}, []) == []

    def test_drop_beyond_threshold_is_flagged(self):
        current = {"recall_at_10": 0.70}
        history = [{"recall_at_10": 0.90}]  # dropped 0.20 > 0.05
        regs = detect_regressions(current, history)
        assert len(regs) == 1
        assert regs[0]["metric"] == "recall_at_10"
        assert regs[0]["degraded_by"] == 0.20

    def test_small_drop_within_threshold_not_flagged(self):
        current = {"faithfulness": 0.87}
        history = [{"faithfulness": 0.90}]  # dropped 0.03 < 0.05
        assert detect_regressions(current, history) == []

    def test_improvement_not_flagged(self):
        current = {"mrr": 0.95}
        history = [{"mrr": 0.70}]
        assert detect_regressions(current, history) == []

    def test_hallucination_increase_is_regression(self):
        # hallucination_rate is lower-is-better: going UP is a regression.
        current = {"hallucination_rate": 0.25}
        history = [{"hallucination_rate": 0.10}]
        regs = detect_regressions(current, history)
        assert [r["metric"] for r in regs] == ["hallucination_rate"]
        assert regs[0]["degraded_by"] == 0.15

    def test_hallucination_decrease_not_flagged(self):
        current = {"hallucination_rate": 0.05}
        history = [{"hallucination_rate": 0.20}]
        assert detect_regressions(current, history) == []

    def test_baseline_averages_recent_runs(self):
        current = {"recall_at_10": 0.60}
        history = [
            {"recall_at_10": 0.80},
            {"recall_at_10": 0.90},
            {"recall_at_10": 1.00},
        ]  # avg = 0.90, drop 0.30
        regs = detect_regressions(current, history)
        assert regs[0]["baseline"] == 0.9
        assert regs[0]["degraded_by"] == 0.30

    def test_missing_metric_is_skipped(self):
        current = {"recall_at_10": 0.5}
        history = [{"mrr": 0.9}]  # no overlapping comparable metric
        assert detect_regressions(current, history) == []
