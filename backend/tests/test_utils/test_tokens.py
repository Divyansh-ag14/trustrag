"""Tests for token counting and truncation utilities."""

from app.utils.tokens import count_tokens, truncate_to_tokens


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        result = count_tokens("hello")
        assert result == 1

    def test_sentence(self):
        result = count_tokens("The quick brown fox jumps over the lazy dog.")
        assert result > 0
        assert result < 20  # sanity — should be ~10 tokens

    def test_long_text(self):
        text = "word " * 1000
        result = count_tokens(text)
        assert result > 500

    def test_special_characters(self):
        result = count_tokens("Hello! @#$%^&*() world 🎉")
        assert result > 0

    def test_code_snippet(self):
        code = "def foo(x): return x + 1\nprint(foo(42))"
        result = count_tokens(code)
        assert result > 5


class TestTruncateToTokens:
    def test_short_text_unchanged(self):
        text = "Hello world"
        result = truncate_to_tokens(text, max_tokens=100)
        assert result == text

    def test_truncation_works(self):
        text = "word " * 200
        result = truncate_to_tokens(text, max_tokens=10)
        assert count_tokens(result) <= 10

    def test_zero_tokens(self):
        result = truncate_to_tokens("some text", max_tokens=0)
        assert result == ""

    def test_exact_token_count(self):
        text = "hello world foo bar"
        n = count_tokens(text)
        result = truncate_to_tokens(text, max_tokens=n)
        assert result == text
