"""Structured logging configuration with structlog."""

import structlog

from app.config import settings


def setup_logging() -> None:
    """Configure structlog with JSON or console rendering based on environment."""
    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.ENVIRONMENT == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_user_context(user_id: str, workspace_id: str, role: str) -> None:
    """Bind user info to structlog context for downstream log calls."""
    structlog.contextvars.bind_contextvars(
        user_id=user_id,
        workspace_id=workspace_id,
        user_role=role,
    )
