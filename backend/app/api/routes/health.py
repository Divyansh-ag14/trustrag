import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.database import async_session_factory, get_qdrant, get_redis

router = APIRouter(tags=["health"])
logger = structlog.get_logger()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    checks = {}

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        logger.error("health.postgres.failed", error=str(e))
        checks["postgres"] = "error"

    try:
        client = get_qdrant()
        client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        logger.error("health.qdrant.failed", error=str(e))
        checks["qdrant"] = "error"

    try:
        redis = get_redis()
        await redis.ping()
        await redis.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error("health.redis.failed", error=str(e))
        checks["redis"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}
