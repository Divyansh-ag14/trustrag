"""Request middleware — request ID, structured logging, rate limiting."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.config import settings
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
    """Simple in-memory sliding window rate limiter.

    In production, replace with Redis-based limiter for
    multi-process deployments.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}

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

        # Clean old entries and add current
        timestamps = self._requests.get(key, [])
        timestamps = [t for t in timestamps if t > window_start]
        timestamps.append(now)
        self._requests[key] = timestamps

        if len(timestamps) > self.max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0]))
            logger.warning(
                "rate_limit.exceeded",
                client_key=key[:20],
                count=len(timestamps),
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": str(max(1, retry_after))},
            )

        return await call_next(request)
