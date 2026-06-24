import re
from dataclasses import dataclass

from app.utils.tokens import count_tokens


@dataclass
class Chunk:
    content: str
    token_count: int
    chunk_index: int
    metadata: dict


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    doc_title: str = "",
) -> list[Chunk]:
    paragraphs = re.split(r"\n\s*\n", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    segments: list[str] = []
    for para in paragraphs:
        if count_tokens(para) > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                segments.append(sent)
        else:
            segments.append(para)

    chunks: list[Chunk] = []
    current_text_parts: list[str] = []
    current_count = 0

    for segment in segments:
        seg_tokens = count_tokens(segment)

        if current_count + seg_tokens > chunk_size and current_text_parts:
            chunk_text_str = "\n\n".join(current_text_parts)
            chunks.append(Chunk(
                content=chunk_text_str,
                token_count=count_tokens(chunk_text_str),
                chunk_index=len(chunks),
                metadata={"source_title": doc_title},
            ))

            overlap_text = ""
            overlap_count = 0
            for part in reversed(current_text_parts):
                part_count = count_tokens(part)
                if overlap_count + part_count > chunk_overlap:
                    break
                overlap_text = part + "\n\n" + overlap_text if overlap_text else part
                overlap_count += part_count

            current_text_parts = [overlap_text] if overlap_text else []
            current_count = overlap_count

        current_text_parts.append(segment)
        current_count += seg_tokens

    if current_text_parts:
        chunk_text_str = "\n\n".join(current_text_parts)
        chunks.append(Chunk(
            content=chunk_text_str,
            token_count=count_tokens(chunk_text_str),
            chunk_index=len(chunks),
            metadata={"source_title": doc_title},
        ))

    return chunks
