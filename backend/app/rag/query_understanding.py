import json
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


QUERY_ANALYSIS_PROMPT = """You are a query analysis engine for an enterprise knowledge base.

Analyze the user's query and return a JSON object with:

1. "rewritten_query": An optimized version of the query for search retrieval.
   - Remove conversational filler ("Can you tell me...", "I was wondering...")
   - Resolve pronouns using session context if provided
   - Expand abbreviations
   - Keep the core information need intact

2. "query_type": One of: factual, procedural, troubleshooting, comparison, multi_hop, conversational

3. "intent": One of: lookup, explain, compare, troubleshoot, summarize, follow_up

4. "date_sensitive": true if the query asks about recent changes, updates, versions, or time-dependent info

5. "ambiguity": "low", "medium", or "high"

6. "metadata_filters": {{
     "source_types": [],  // LEAVE EMPTY unless the user EXPLICITLY names a source/type to restrict to.
                          // Valid values: "pdf", "markdown", "text", "html", "csv", "faq",
                          // "slack_export", "release_note", "notion", "github", "web".
                          // Only set this if the query says things like "in the PDFs",
                          // "from Slack", "in our Notion", "the GitHub issues". For a general
                          // question, ALWAYS return [] — never guess a list of types.
     "date_range": {{}}   // e.g. {{"after": "2025-01-01"}} if query implies a time range
   }}

Return ONLY valid JSON, no markdown fences."""


@dataclass
class QueryAnalysis:
    rewritten_query: str
    query_type: str = "factual"
    intent: str = "lookup"
    date_sensitive: bool = False
    ambiguity: str = "low"
    metadata_filters: dict = field(default_factory=dict)
    raw_query: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


def analyze_query(
    query: str,
    session_context: list[dict] | None = None,
) -> QueryAnalysis:
    client = _get_client()

    context_text = ""
    if session_context:
        recent = session_context[-4:]
        context_text = "\n\nRecent conversation context:\n"
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]
            context_text += f"- {role}: {content}\n"

    user_msg = f"Query: {query}{context_text}"

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": QUERY_ANALYSIS_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
        )

        content = response.choices[0].message.content or "{}"
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
        if content.endswith("```"):
            content = content[:-3]

        parsed = json.loads(content.strip())
        usage = response.usage

        analysis = QueryAnalysis(
            rewritten_query=parsed.get("rewritten_query", query),
            query_type=parsed.get("query_type", "factual"),
            intent=parsed.get("intent", "lookup"),
            date_sensitive=parsed.get("date_sensitive", False),
            ambiguity=parsed.get("ambiguity", "low"),
            metadata_filters=parsed.get("metadata_filters", {}),
            raw_query=query,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

        logger.info(
            "query_understanding.complete",
            query_type=analysis.query_type,
            intent=analysis.intent,
            date_sensitive=analysis.date_sensitive,
            rewritten=analysis.rewritten_query[:100],
        )

        return analysis

    except Exception as e:
        logger.warning("query_understanding.failed", error=str(e))
        return QueryAnalysis(
            rewritten_query=query,
            raw_query=query,
        )
