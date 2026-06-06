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


HALLUCINATION_CHECK_SYSTEM = """You are a faithfulness verification engine. Given a context and a list of sentences extracted from an AI-generated answer, classify each one.

For each sentence, classify it as:
- "entailed": it asserts a fact about the subject and the context directly supports it
- "neutral": it asserts a fact about the subject but the context neither supports nor contradicts it (it may be true but is not verifiable from the context)
- "contradicted": it asserts a fact about the subject and the context contradicts it
- "not_a_claim": it makes NO verifiable assertion about the subject — pure framing, conversational filler, a transition, a pointer to sources, or meta-commentary about the answer itself. Examples: "Here's what I found.", "According to the documentation:", "I hope this helps.", "Let me explain.", a question, a heading.

CRITICAL: Use "not_a_claim" ONLY for non-assertive filler. ANY sentence stating a fact about the subject — even if that fact is wrong or unverifiable — is a claim and must be "entailed", "neutral", or "contradicted". When unsure whether something asserts a fact, treat it as a claim, not as "not_a_claim".

Return a JSON array of objects with:
- "claim": the sentence text
- "verdict": one of "entailed", "neutral", "contradicted", "not_a_claim"
- "reason": brief explanation (max 20 words)

Return ONLY valid JSON, no markdown fences."""


@dataclass
class ClaimVerdict:
    claim: str
    verdict: str  # entailed, neutral, contradicted
    reason: str = ""


# Max context chars sent to the NLI check. The built context is token-budgeted
# (~4000 tokens ≈ 16000 chars); truncating much below that mislabels claims
# supported by later context as "neutral" → false hallucination flags.
MAX_CONTEXT_CHARS = 16000


@dataclass
class HallucinationResult:
    faithfulness_score: float | None = 1.0
    hallucination_score: float | None = 0.0
    claim_verdicts: list[ClaimVerdict] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    contradicted_claims: list[str] = field(default_factory=list)
    action: str = "pass"  # pass, disclaimer, block
    verification_failed: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0


def _split_into_claims(answer: str) -> list[str]:
    """Split answer into atomic claims.

    Splits on line boundaries first (so bulleted/numbered list items become
    separate claims instead of one giant run-on), then on sentence boundaries
    within each line.
    """
    clean = re.sub(r'\[\d+\]', '', answer)
    clean = re.sub(
        r"^I'm not confident in a complete answer, but here's what I found:\s*",
        '',
        clean,
    )

    claims = []
    for line in clean.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip leading bullet/numbering markers ("- ", "* ", "1. ", "2) ")
        line = re.sub(r'^([-*•]|\d+[.)])\s+', '', line).strip()
        for s in re.split(r'(?<=[.!?])\s+', line):
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

    try:
        client = _get_client()

        user_msg = json.dumps({
            "context": context[:MAX_CONTEXT_CHARS],
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
        scored_count = 0  # claims that actually assert a fact (excludes not_a_claim)
        unsupported = []
        contradicted = []

        for item in results:
            verdict = ClaimVerdict(
                claim=item.get("claim", ""),
                verdict=item.get("verdict", "entailed"),
                reason=item.get("reason", ""),
            )
            verdicts.append(verdict)

            if verdict.verdict == "not_a_claim":
                # Pure framing/filler — not a factual assertion, so it must not
                # count for or against faithfulness.
                continue

            scored_count += 1
            if verdict.verdict == "entailed":
                entailed_count += 1
            elif verdict.verdict == "neutral":
                unsupported.append(verdict.claim)
            elif verdict.verdict == "contradicted":
                contradicted.append(verdict.claim)

        # If the answer was entirely non-assertive (no real claims), there is
        # nothing to hallucinate — treat as faithful.
        if scored_count == 0:
            faithfulness = 1.0
        else:
            faithfulness = entailed_count / scored_count
        hallucination = 1.0 - faithfulness

        if hallucination <= 0.1:
            action = "pass"
        elif hallucination <= 0.3:
            action = "disclaimer"
        else:
            action = "block"

        logger.info(
            "hallucination_checker.complete",
            scored_claims=scored_count,
            not_a_claim=len(verdicts) - scored_count,
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
        # Fail toward caution, NOT open. If the verifier itself breaks we must
        # not ship an unverified answer as if it passed. Mark scores unknown
        # (None → excluded from quality averages) and surface a disclaimer.
        logger.warning("hallucination_checker.failed", error=str(e))
        return HallucinationResult(
            faithfulness_score=None,
            hallucination_score=None,
            action="disclaimer",
            verification_failed=True,
        )
