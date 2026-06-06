"""Tests for the hallucination checker — fail-closed behavior and claim splitting.

The most important property: when the NLI verifier itself errors, the checker
must NOT ship the answer as if it passed verification (no fail-open).
"""

from types import SimpleNamespace
from unittest.mock import patch

from app.rag.hallucination_checker import (
    HallucinationResult,
    _split_into_claims,
    check_hallucination,
)


def _fake_response(verdicts: list[dict], prompt_tokens: int = 10, completion_tokens: int = 5):
    """Build a fake OpenAI chat completion whose content is the NLI JSON array."""
    import json

    message = SimpleNamespace(content=json.dumps(verdicts))
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage)


def _client_returning(verdicts: list[dict]):
    """A fake OpenAI client whose chat.completions.create returns the given verdicts."""
    create = lambda **kwargs: _fake_response(verdicts)  # noqa: E731
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestFailClosed:
    @patch("app.rag.hallucination_checker._get_client")
    def test_verifier_error_does_not_fail_open(self, mock_get_client):
        # Verifier blows up (API failure, timeout, malformed JSON, etc.)
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("API down")

        result = check_hallucination(
            "Enterprise customers get a full refund within 30 days.",
            "Some retrieved context that does support refunds.",
        )

        # The critical assertion: it must NOT pass an unverified answer.
        assert result.action != "pass"
        assert result.action == "disclaimer"
        assert result.verification_failed is True

    @patch("app.rag.hallucination_checker._get_client")
    def test_verifier_error_marks_scores_unknown(self, mock_get_client):
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("boom")

        result = check_hallucination("A claim that is long enough to count.", "context text")

        # Scores are unknown (None) so they don't pollute quality averages as
        # either a fake-perfect 1.0 or a fake-terrible 0.0.
        assert result.faithfulness_score is None
        assert result.hallucination_score is None

    @patch("app.rag.hallucination_checker._get_client")
    def test_client_init_failure_also_fails_closed(self, mock_get_client):
        # Even if constructing the client raises, we must fail closed.
        mock_get_client.side_effect = Exception("no api key")

        result = check_hallucination("A claim that is long enough to count.", "context text")

        assert result.action == "disclaimer"
        assert result.verification_failed is True


class TestThresholds:
    @patch("app.rag.hallucination_checker._get_client")
    def test_all_entailed_passes(self, mock_get_client):
        mock_get_client.return_value = _client_returning([
            {"claim": "Enterprise customers get a full refund within 30 days.", "verdict": "entailed"},
        ])
        result = check_hallucination(
            "Enterprise customers get a full refund within 30 days.",
            "Refund policy context.",
        )
        assert result.action == "pass"
        assert result.faithfulness_score == 1.0
        assert result.verification_failed is False

    @patch("app.rag.hallucination_checker._get_client")
    def test_mostly_unsupported_blocks(self, mock_get_client):
        mock_get_client.return_value = _client_returning([
            {"claim": "First claim here that is long.", "verdict": "neutral"},
            {"claim": "Second claim here that is long.", "verdict": "contradicted"},
            {"claim": "Third claim here that is long.", "verdict": "neutral"},
        ])
        result = check_hallucination(
            "First claim here that is long. Second claim here that is long. Third claim here that is long.",
            "Unrelated context.",
        )
        # 0/3 entailed → hallucination 1.0 → block
        assert result.action == "block"


class TestNotAClaim:
    """Framing/filler sentences must not drag faithfulness down (false-positive fix)."""

    @patch("app.rag.hallucination_checker._get_client")
    def test_framing_sentence_does_not_block_valid_answer(self, mock_get_client):
        # The exact bug: a real fact (entailed) + a framing sentence the NLI
        # can't entail. Before the fix this scored 0.5 → block.
        mock_get_client.return_value = _client_returning([
            {"claim": "The Pro plan supports up to 50 users.", "verdict": "entailed"},
            {"claim": "According to the onboarding guide:", "verdict": "not_a_claim"},
        ])
        result = check_hallucination(
            "The Pro plan supports up to 50 users. According to the onboarding guide:",
            "Each workspace supports up to 50 users on the Pro plan.",
        )
        assert result.action == "pass"
        assert result.faithfulness_score == 1.0

    @patch("app.rag.hallucination_checker._get_client")
    def test_all_framing_passes(self, mock_get_client):
        mock_get_client.return_value = _client_returning([
            {"claim": "Here's what I found.", "verdict": "not_a_claim"},
            {"claim": "I hope this helps.", "verdict": "not_a_claim"},
        ])
        result = check_hallucination("Here's what I found. I hope this helps.", "ctx")
        assert result.action == "pass"
        assert result.faithfulness_score == 1.0

    @patch("app.rag.hallucination_checker._get_client")
    def test_detection_not_weakened_real_fabrication_still_blocks(self, mock_get_client):
        # A framing line plus a genuine fabricated fact (neutral) → the fact is
        # still scored, so faithfulness stays low and the answer is blocked.
        mock_get_client.return_value = _client_returning([
            {"claim": "Here's what I found.", "verdict": "not_a_claim"},
            {"claim": "The Pro plan supports up to 9000 users.", "verdict": "neutral"},
        ])
        result = check_hallucination(
            "Here's what I found. The Pro plan supports up to 9000 users.",
            "Each workspace supports up to 50 users on the Pro plan.",
        )
        # 0 entailed / 1 scored claim → hallucination 1.0 → block
        assert result.action == "block"

    @patch("app.rag.hallucination_checker._get_client")
    def test_contradiction_still_blocks_with_framing(self, mock_get_client):
        mock_get_client.return_value = _client_returning([
            {"claim": "Let me explain.", "verdict": "not_a_claim"},
            {"claim": "Refunds are never allowed.", "verdict": "contradicted"},
        ])
        result = check_hallucination(
            "Let me explain. Refunds are never allowed.",
            "Enterprise customers can request a full refund within 30 days.",
        )
        assert result.action == "block"


class TestEdgeCases:
    def test_empty_context_blocks(self):
        result = check_hallucination("A real claim that is long enough.", "   ")
        assert result.action == "block"
        assert result.hallucination_score == 1.0

    def test_no_claims_passes(self):
        # Nothing substantive to verify (e.g. a one-word refusal).
        result = check_hallucination("OK.", "some context")
        assert result.action == "pass"
        assert result.verification_failed is False


class TestClaimSplitting:
    def test_strips_citation_markers(self):
        claims = _split_into_claims("Refunds are allowed [1] within 30 days [2].")
        assert all("[" not in c for c in claims)

    def test_bulleted_list_becomes_separate_claims(self):
        answer = (
            "The plan includes:\n"
            "- Full refunds within 30 days\n"
            "- Prorated refunds for annual plans\n"
            "- No refunds after cancellation"
        )
        claims = _split_into_claims(answer)
        # Each bullet should be its own claim (markers stripped), not one blob.
        assert any("Full refunds within 30 days" in c for c in claims)
        assert any("Prorated refunds for annual plans" in c for c in claims)
        assert any("No refunds after cancellation" in c for c in claims)
        # Bullet markers should be removed from the front.
        assert all(not c.startswith(("-", "*", "•")) for c in claims)

    def test_skips_note_lines(self):
        claims = _split_into_claims("This is a supported claim here.\nNote: this is a disclaimer line.")
        assert any("supported claim" in c for c in claims)
        assert all(not c.startswith("Note:") for c in claims)

    def test_drops_trivially_short_fragments(self):
        claims = _split_into_claims("Yes. This one is a long enough claim to keep.")
        assert all(len(c) > 10 for c in claims)


class TestResultDefaults:
    def test_default_is_clean_pass(self):
        # Sanity: the dataclass default still represents a clean pass for the
        # happy paths that intentionally return HallucinationResult().
        r = HallucinationResult()
        assert r.action == "pass"
        assert r.verification_failed is False
        assert r.faithfulness_score == 1.0
