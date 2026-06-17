"""Request middleware — request ID, structured logging, rate limiting."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.database import get_redis
from app.services.auth_service import decode_token

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind request context for all downstream logs
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
        )

        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.error(
                "request.error",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                error=str(exc),
            )
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id

        # Skip noisy health check logs
        if request.url.path not in ("/health", "/health/ready"):
            log_level = "info" if response.status_code < 400 else "warning"
            getattr(logger, log_level)(
                "request.completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter.

    Uses a per-key Redis sorted set so the limit is shared across all worker
    processes and instances (an in-memory limiter would give each process its
    own bucket = N_workers × the limit). Fails open if Redis is unavailable so
    the API stays up even if the limiter's backing store is down.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._redis = get_redis()

    def _get_client_key(self, request: Request) -> str | None:
        # Only rate-limit API endpoints
        if not request.url.path.startswith("/api/"):
            return None

        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # Key on the authenticated user id (JWT "sub"), not the token
            # prefix. Every HS256 token shares the same header prefix, so
            # keying on the prefix collapses all users into one bucket.
            payload = decode_token(auth[7:])
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
            # Invalid/expired token → fall through to IP-based limiting; the
            # auth layer will reject the request anyway.

        # Fall back to IP for unauthenticated/invalid-token requests
        client = request.client
        if client:
            return f"ip:{client.host}"
        return None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        key = self._get_client_key(request)
        if not key:
            return await call_next(request)

        now = time.time()
        window_start = now - self.window_seconds
        redis_key = f"ratelimit:{key}"

        try:
            # Sliding window via sorted set: drop old entries, add this request,
            # count what's left in the window — all atomically in one pipeline.
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(redis_key, 0, window_start)
            pipe.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, self.window_seconds)
            results = await pipe.execute()
            count = results[2]
        except Exception as e:
            # Fail open: never take down the API because the limiter store is down.
            logger.warning("rate_limit.redis_unavailable", error=str(e))
            return await call_next(request)

        if count > self.max_requests:
            retry_after = self.window_seconds
            try:
                oldest = await self._redis.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    retry_after = max(1, int(self.window_seconds - (now - oldest[0][1])))
            except Exception:
                pass
            logger.warning("rate_limit.exceeded", client_key=key[:20], count=count)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
