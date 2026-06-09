"""Tests for query understanding — token usage capture (cost tracking).

Regression target: analyze_query discarded response.usage, so the pipeline
counted query-understanding tokens as zero and understated cost_usd.
"""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.rag.query_understanding import analyze_query


def _client_returning(payload: dict, prompt_tokens: int, completion_tokens: int):
    message = SimpleNamespace(content=json.dumps(payload))
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    response = SimpleNamespace(choices=[choice], usage=usage)
    create = lambda **kwargs: response  # noqa: E731
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestTokenCapture:
    @patch("app.rag.query_understanding._get_client")
    def test_captures_usage_tokens(self, mock_get_client):
        mock_get_client.return_value = _client_returning(
            {"rewritten_query": "what is the refund policy", "query_type": "factual"},
            prompt_tokens=120,
            completion_tokens=18,
        )
        analysis = analyze_query("tell me about refunds")
        assert analysis.prompt_tokens == 120
        assert analysis.completion_tokens == 18
        assert analysis.rewritten_query == "what is the refund policy"

    @patch("app.rag.query_understanding._get_client")
    def test_fallback_has_zero_tokens(self, mock_get_client):
        mock_get_client.return_value.chat.completions.create.side_effect = Exception("api down")
        analysis = analyze_query("anything")
        assert analysis.prompt_tokens == 0
        assert analysis.completion_tokens == 0
        # Falls back to the raw query
        assert analysis.rewritten_query == "anything"
