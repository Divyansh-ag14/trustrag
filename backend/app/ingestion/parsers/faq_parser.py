"""Parse FAQ-format files (Markdown or JSON) into Q&A blocks.

Supports two formats:
1. Markdown with ## headings as questions and body as answers
2. JSON array of {"question": "...", "answer": "..."} objects

Each Q&A pair becomes a separate block for better retrieval precision.
"""

import json
import re


class FAQParser:
    @staticmethod
    def parse(file_path: str) -> str:
        if file_path.endswith(".json"):
            return _parse_json_faq(file_path)
        return _parse_markdown_faq(file_path)


def _parse_json_faq(file_path: str) -> str:
    with open(file_path) as f:
        data = json.load(f)

    if not isinstance(data, list):
        data = data.get("faqs", data.get("items", data.get("questions", [])))

    parts = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = item.get("question", item.get("q", "")).strip()
        a = item.get("answer", item.get("a", "")).strip()
        if q and a:
            parts.append(f"Q: {q}\nA: {a}")

    return "\n\n---\n\n".join(parts)


def _parse_markdown_faq(file_path: str) -> str:
    with open(file_path) as f:
        content = f.read()

    # Split on ## headings (FAQ questions)
    sections = re.split(r'^##\s+', content, flags=re.MULTILINE)

    parts = []
    for section in sections[1:]:  # skip content before first ##
        lines = section.strip().split("\n", 1)
        question = lines[0].strip().rstrip("?") + "?"
        answer = lines[1].strip() if len(lines) > 1 else ""
        if question and answer:
            parts.append(f"Q: {question}\nA: {answer}")

    if not parts:
        # Fallback: return raw content if no ## headings found
        return content.strip()

    return "\n\n---\n\n".join(parts)
