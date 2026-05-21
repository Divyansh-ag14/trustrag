import json
import re
from dataclasses import dataclass, field

import structlog
from openai import OpenAI

from app.config import settings

logger = structlog.get_logger()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


HALLUCINATION_CHECK_SYSTEM = """You are a faithfulness verification engine. Given a context and a list of claims extracted from an AI-generated answer, determine if each claim is supported by the context.

For each claim, classify it as:
- "entailed": the context directly supports this claim
- "neutral": the context neither supports nor contradicts this claim (the claim may be true but is not verifiable from the context)
- "contradicted": the context contradicts this claim

Return a JSON array of objects with:
- "claim": the claim text
- "verdict": one of "entailed", "neutral", "contradicted"
- "reason": brief explanation (max 20 words)

Return ONLY valid JSON, no markdown fences."""


@dataclass
class ClaimVerdict:
    claim: str
    verdict: str  # entailed, neutral, contradicted
    reason: str = ""


@dataclass
class HallucinationResult:
    faithfulness_score: float = 1.0
    hallucination_score: float = 0.0
    claim_verdicts: list[ClaimVerdict] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    contradicted_claims: list[str] = field(default_factory=list)
    action: str = "pass"  # pass, disclaimer, block
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _split_into_claims(answer: str) -> list[str]:
    """Split answer into atomic claims at sentence level."""
    clean = re.sub(r'\[\d+\]', '', answer)
    clean = re.sub(
        r"^I'm not confident in a complete answer, but here's what I found:\s*",
        '',
        clean,
    )

    sentences = re.split(r'(?<=[.!?])\s+', clean.strip())
    claims = []
    for s in sentences:
        s = s.strip()
        if len(s) > 10 and not s.startswith("Note:"):
            claims.append(s)

    return claims


def check_hallucination(
    answer: str,
    context: str,
) -> HallucinationResult:
    claims = _split_into_claims(answer)
    if not claims:
        return HallucinationResult()

    if not context.strip():
        return HallucinationResult(
            faithfulness_score=0.0,
            hallucination_score=1.0,
            action="block",
        )

    client = _get_client()

    try:
        user_msg = json.dumps({
            "context": context[:3000],
            "claims": claims,
        })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": HALLUCINATION_CHECK_SYSTEM},
                {"role": "user", "content": user_msg},
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
        entailed_count = 0
        unsupported = []
        contradicted = []

        for item in results:
            verdict = ClaimVerdict(
                claim=item.get("claim", ""),
                verdict=item.get("verdict", "entailed"),
                reason=item.get("reason", ""),
            )
            verdicts.append(verdict)

            if verdict.verdict == "entailed":
                entailed_count += 1
            elif verdict.verdict == "neutral":
                unsupported.append(verdict.claim)
            elif verdict.verdict == "contradicted":
                contradicted.append(verdict.claim)

        total = len(verdicts) if verdicts else 1
        faithfulness = entailed_count / total
        hallucination = 1.0 - faithfulness

        if hallucination <= 0.1:
            action = "pass"
        elif hallucination <= 0.3:
            action = "disclaimer"
        else:
            action = "block"

        logger.info(
            "hallucination_checker.complete",
            total_claims=total,
            entailed=entailed_count,
            unsupported=len(unsupported),
            contradicted=len(contradicted),
            faithfulness=faithfulness,
            action=action,
        )

        return HallucinationResult(
            faithfulness_score=faithfulness,
            hallucination_score=hallucination,
            claim_verdicts=verdicts,
            unsupported_claims=unsupported,
            contradicted_claims=contradicted,
            action=action,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    except Exception as e:
        logger.warning("hallucination_checker.failed", error=str(e))
        return HallucinationResult()
