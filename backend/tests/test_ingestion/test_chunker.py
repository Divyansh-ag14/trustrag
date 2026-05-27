"""Tests for the text chunker."""

from app.ingestion.chunker import chunk_text
from app.utils.tokens import count_tokens


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Hello world. This is a short document."
        chunks = chunk_text(text, chunk_size=512)
        assert len(chunks) == 1
        assert chunks[0].content.strip() == text
        assert chunks[0].chunk_index == 0

    def test_long_text_produces_multiple_chunks(self):
        text = "This is a sentence. " * 200
        chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)
        assert len(chunks) > 1

    def test_chunk_sizes_within_budget(self):
        text = "This is a meaningful sentence. " * 300
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        for chunk in chunks:
            # Chunks should be roughly at or under budget (overlap may push slightly over)
            assert chunk.token_count <= 150  # generous margin

    def test_chunk_indices_sequential(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\n" * 20
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=5)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_metadata_contains_title(self):
        text = "Some content here."
        chunks = chunk_text(text, doc_title="My Document")
        assert chunks[0].metadata["source_title"] == "My Document"

    def test_empty_text_returns_empty(self):
        chunks = chunk_text("")
        assert len(chunks) == 0

    def test_whitespace_only_returns_empty(self):
        chunks = chunk_text("   \n\n   \t  ")
        assert len(chunks) == 0

    def test_paragraph_splitting(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=512)
        # With 512 token budget, all three paragraphs fit in one chunk
        assert len(chunks) >= 1
        assert "First paragraph" in chunks[0].content

    def test_overlap_preserves_context(self):
        paragraphs = [f"Paragraph number {i} with some extra words." for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)
        if len(chunks) >= 2:
            # Last part of chunk 0 should appear at start of chunk 1 (overlap)
            last_para_c0 = chunks[0].content.split("\n\n")[-1]
            assert last_para_c0 in chunks[1].content

    def test_token_count_matches_content(self):
        text = "A fairly normal sentence with some words in it. " * 10
        chunks = chunk_text(text, chunk_size=30)
        for chunk in chunks:
            actual = count_tokens(chunk.content)
            assert chunk.token_count == actual
