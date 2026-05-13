import hashlib
import json

import structlog
from openai import OpenAI

from app.config import settings
from app.database import get_redis

logger = structlog.get_logger()

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    client = _get_client()
    all_embeddings: list[list[float]] = []

    redis = get_redis()
    try:
        uncached_indices: list[int] = []
        cached_embeddings: dict[int, list[float]] = {}

        for i, text in enumerate(texts):
            cache_key = f"emb:{_content_hash(text)}"
            cached = await redis.get(cache_key)
            if cached:
                cached_embeddings[i] = json.loads(cached)
            else:
                uncached_indices.append(i)

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]

            for start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[start : start + batch_size]
                response = client.embeddings.create(
                    model=settings.EMBEDDING_MODEL,
                    input=batch,
                )
                for j, item in enumerate(response.data):
                    idx = uncached_indices[start + j]
                    cached_embeddings[idx] = item.embedding

                    cache_key = f"emb:{_content_hash(texts[idx])}"
                    await redis.set(cache_key, json.dumps(item.embedding))

            logger.info(
                "embedder.batch_complete",
                total=len(texts),
                cached=len(texts) - len(uncached_indices),
                computed=len(uncached_indices),
            )

        all_embeddings = [cached_embeddings[i] for i in range(len(texts))]
    except Exception:
        logger.warning("embedder.cache_unavailable, falling back to direct embedding")
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=batch,
            )
            all_embeddings.extend([item.embedding for item in response.data])
    finally:
        try:
            await redis.aclose()
        except Exception:
            pass

    return all_embeddings


def embed_single(text: str) -> list[float]:
    client = _get_client()
    response = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=text)
    return response.data[0].embedding
