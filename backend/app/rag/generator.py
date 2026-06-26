import json
from dataclasses import dataclass

import structlog
from openai import OpenAI

from app.config import settings
from app.rag.prompts import (
    GROUNDED_GENERATION_STREAM_SYSTEM,
    GROUNDED_GENERATION_SYSTEM,
    GROUNDED_GENERATION_USER,
)

logger = structlog.get_logger()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


@dataclass
class GenerationResult:
    answer: str
    citations_used: list[int]
    confidence: float
    has_conflicts: bool
    follow_up_suggestions: list[str]
    escalation_needed: bool
    escalation_reason: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _parse_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {
            "answer": content,
            "citations_used": [],
            "confidence": 0.5,
            "has_conflicts": False,
            "follow_up_suggestions": [],
            "escalation_needed": False,
            "escalation_reason": None,
        }


def generate(
    query: str,
    context: str,
    workspace_name: str = "your organization",
) -> GenerationResult:
    client = _get_client()

    if not context.strip():
        return GenerationResult(
            answer="I couldn't find relevant information for this question in the knowledge base.",
            citations_used=[],
            confidence=0.0,
            has_conflicts=False,
            follow_up_suggestions=[],
            escalation_needed=False,
            escalation_reason=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )

    system_msg = GROUNDED_GENERATION_SYSTEM.format(workspace_name=workspace_name)
    user_msg = GROUNDED_GENERATION_USER.format(context=context, query=query)

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=settings.LLM_TEMPERATURE,
    )

    content = response.choices[0].message.content or ""
    usage = response.usage

    parsed = _parse_response(content)

    confidence = parsed.get("confidence", 0.5)
    answer = parsed.get("answer", content)

    if confidence < 0.6:
        answer = (
            "I'm not confident in a complete answer, but here's what I found:\n\n"
            + answer
        )

    logger.info(
        "generator.complete",
        confidence=confidence,
        citations=len(parsed.get("citations_used", [])),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )

    return GenerationResult(
        answer=answer,
        citations_used=parsed.get("citations_used", []),
        confidence=confidence,
        has_conflicts=parsed.get("has_conflicts", False),
        follow_up_suggestions=parsed.get("follow_up_suggestions", []),
        escalation_needed=parsed.get("escalation_needed", False),
        escalation_reason=parsed.get("escalation_reason"),
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
    )


def generate_stream(
    query: str,
    context: str,
    workspace_name: str = "your organization",
):
    client = _get_client()

    if not context.strip():
        yield {
            "type": "answer",
            "data": "I couldn't find relevant information for this question in the knowledge base.",
        }
        yield {
            "type": "metadata",
            "data": {
                "confidence": 0.0,
                "citations_used": [],
                "has_conflicts": False,
                "follow_up_suggestions": [],
            },
        }
        return

    system_msg = GROUNDED_GENERATION_SYSTEM.format(workspace_name=workspace_name)
    user_msg = GROUNDED_GENERATION_USER.format(context=context, query=query)

    stream = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=settings.LLM_TEMPERATURE,
        stream=True,
        stream_options={"include_usage": True},
    )

    full_content = ""
    usage_data = None

    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_content += token
            yield {"type": "token", "data": token}

        if chunk.usage:
            usage_data = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }

    parsed = _parse_response(full_content)

    yield {
        "type": "metadata",
        "data": {
            "confidence": parsed.get("confidence", 0.5),
            "citations_used": parsed.get("citations_used", []),
            "has_conflicts": parsed.get("has_conflicts", False),
            "follow_up_suggestions": parsed.get("follow_up_suggestions", []),
            "escalation_needed": parsed.get("escalation_needed", False),
            "usage": usage_data,
        },
    }


def generate_answer_stream(query: str, context: str, workspace_name: str = "your organization"):
    """Stream a plain-text grounded answer (clean tokens, no JSON wrapper).

    Yields {"type": "token", "data": str} per token, then a final
    {"type": "usage", "data": {prompt_tokens, completion_tokens, total_tokens}}.
    Confidence + citations are derived afterward (faithfulness check + [N] markers).
    """
    client = _get_client()
    system_msg = GROUNDED_GENERATION_STREAM_SYSTEM.format(workspace_name=workspace_name)
    user_msg = GROUNDED_GENERATION_USER.format(context=context, query=query)

    stream = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=settings.LLM_TEMPERATURE,
        stream=True,
        stream_options={"include_usage": True},
    )

    usage_data = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield {"type": "token", "data": chunk.choices[0].delta.content}
        if chunk.usage:
            usage_data = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }

    yield {"type": "usage", "data": usage_data}
