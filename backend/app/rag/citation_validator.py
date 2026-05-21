import json
import re
from dataclasses import dataclass, field

import structlog
from openai import OpenAI

from app.config import settings
from app.rag.retriever import RetrievedChunk

logger = structlog.get_logger()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


CITATION_VALIDATION_SYSTEM = """You are a citation verification engine. For each citation pair (claim + source), determine if the source supports the claim.

You will receive a JSON array of objects, each with "claim" and "source" fields.

Return a JSON array of objects with:
- "index": the citation index
- "verdict": one of "supported", "partially_supported", "not_supported"

Return ONLY valid JSON, no markdown fences."""


@dataclass
class CitationVerdict:
    index: int
    claim: str
    verdict: str  # supported, partially_supported, not_supported


@dataclass
class CitationValidationResult:
    verdicts: list[CitationVerdict] = field(default_factory=list)
    citation_accuracy: float = 1.0
    unsupported_citations: list[int] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _extract_citation_claims(answer: str) -> list[tuple[int, str]]:
    """Extract (citation_index, surrounding_sentence) pairs from the answer."""
    sentences = re.split(r'(?<=[.!?])\s+', answer)
    claims = []
    seen_indices = set()

    for sentence in sentences:
        citation_matches = re.findall(r'\[(\d+)\]', sentence)
        for match in citation_matches:
            idx = int(match)
            if idx not in seen_indices:
                clean_sentence = re.sub(r'\[\d+\]', '', sentence).strip()
                if clean_sentence:
                    claims.append((idx, clean_sentence))
                    seen_indices.add(idx)

    return claims


def validate_citations(
    answer: str,
    citations_used: list[int],
    chunks_used: list[RetrievedChunk],
) -> CitationValidationResult:
    if not citations_used or not chunks_used:
        return CitationValidationResult()

    claims = _extract_citation_claims(answer)
    if not claims:
        return CitationValidationResult()

    pairs = []
    for idx, claim in claims:
        if 1 <= idx <= len(chunks_used):
            source_content = chunks_used[idx - 1].content[:500]
            pairs.append({
                "index": idx,
                "claim": claim,
                "source": source_content,
            })

    if not pairs:
        return CitationValidationResult()

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": CITATION_VALIDATION_SYSTEM},
                {"role": "user", "content": json.dumps(pairs)},
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content or "[]"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]

        results = json.loads(content.strip())
        usage = response.usage

        verdicts = []
        supported_count = 0
        unsupported = []

        for item in results:
            verdict = CitationVerdict(
                index=item.get("index", 0),
                claim=next(
                    (p["claim"] for p in pairs if p["index"] == item.get("index")),
                    "",
                ),
                verdict=item.get("verdict", "supported"),
            )
            verdicts.append(verdict)

            if verdict.verdict == "supported":
                supported_count += 1
            elif verdict.verdict == "not_supported":
                unsupported.append(verdict.index)

        accuracy = supported_count / len(verdicts) if verdicts else 1.0

        logger.info(
            "citation_validator.complete",
            total_citations=len(verdicts),
            supported=supported_count,
            unsupported=len(unsupported),
            accuracy=accuracy,
        )

        return CitationValidationResult(
            verdicts=verdicts,
            citation_accuracy=accuracy,
            unsupported_citations=unsupported,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    except Exception as e:
        logger.warning("citation_validator.failed", error=str(e))
        return CitationValidationResult()
