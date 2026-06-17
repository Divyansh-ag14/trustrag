"""Analytics API routes — usage, quality, cost, and latency aggregation."""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _date_range(
    days: int | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if date_from and date_to:
        start = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        end = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
    else:
        d = days or 30
        start = now - timedelta(days=d)
        end = now
    return start, end


@router.get("/usage")
async def get_usage_analytics(
    days: int | None = Query(30, ge=1, le=365),
    date_from: str | None = None,
    date_to: str | None = None,
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start, end = _date_range(days, date_from, date_to)
    workspace_id = str(user.workspace_id)

    trunc = {"day": "day", "week": "week", "month": "month"}[granularity]

    sql = text("""
        SELECT
            date_trunc(:trunc, q.created_at) AS period,
            COUNT(*) AS query_count,
            COUNT(DISTINCT q.user_id) AS unique_users
        FROM queries q
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
        GROUP BY period
        ORDER BY period
    """)
    result = await db.execute(sql, {
        "trunc": trunc, "wid": workspace_id,
        "start": start, "end_dt": end,
    })
    volume = [
        {
            "period": row.period.isoformat(),
            "query_count": row.query_count,
            "unique_users": row.unique_users,
        }
        for row in result.fetchall()
    ]

    # Totals
    totals_sql = text("""
        SELECT
            COUNT(*) AS total_queries,
            COUNT(DISTINCT q.user_id) AS total_users,
            COUNT(DISTINCT q.session_id) AS total_sessions
        FROM queries q
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
    """)
    totals_row = (await db.execute(totals_sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchone()

    # Status breakdown
    status_sql = text("""
        SELECT
            qr.status,
            COUNT(*) AS count
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
        GROUP BY qr.status
    """)
    status_rows = (await db.execute(status_sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchall()
    status_breakdown = {row.status: row.count for row in status_rows}

    return {
        "total_queries": totals_row.total_queries if totals_row else 0,
        "total_users": totals_row.total_users if totals_row else 0,
        "total_sessions": totals_row.total_sessions if totals_row else 0,
        "status_breakdown": status_breakdown,
        "volume": volume,
    }


@router.get("/quality")
async def get_quality_analytics(
    days: int | None = Query(30, ge=1, le=365),
    date_from: str | None = None,
    date_to: str | None = None,
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start, end = _date_range(days, date_from, date_to)
    workspace_id = str(user.workspace_id)
    trunc = {"day": "day", "week": "week", "month": "month"}[granularity]

    sql = text("""
        SELECT
            date_trunc(:trunc, q.created_at) AS period,
            AVG(qr.confidence_score) AS avg_confidence,
            AVG(qr.faithfulness_score) AS avg_faithfulness,
            AVG(qr.citation_accuracy) AS avg_citation_accuracy,
            AVG(qr.hallucination_score) AS avg_hallucination,
            COUNT(*) AS count
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.status != 'error'
        GROUP BY period
        ORDER BY period
    """)
    result = await db.execute(sql, {
        "trunc": trunc, "wid": workspace_id,
        "start": start, "end_dt": end,
    })
    trends = [
        {
            "period": row.period.isoformat(),
            "avg_confidence": round(float(row.avg_confidence or 0), 3),
            "avg_faithfulness": round(float(row.avg_faithfulness or 0), 3),
            "avg_citation_accuracy": round(float(row.avg_citation_accuracy or 0), 3),
            "avg_hallucination": round(float(row.avg_hallucination or 0), 3),
            "count": row.count,
        }
        for row in result.fetchall()
    ]

    # Overall averages
    summary_sql = text("""
        SELECT
            AVG(qr.confidence_score) AS avg_confidence,
            AVG(qr.faithfulness_score) AS avg_faithfulness,
            AVG(qr.citation_accuracy) AS avg_citation_accuracy,
            AVG(qr.hallucination_score) AS avg_hallucination
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.status != 'error'
    """)
    summary = (await db.execute(summary_sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchone()

    return {
        "avg_confidence": round(float(summary.avg_confidence or 0), 3),
        "avg_faithfulness": round(float(summary.avg_faithfulness or 0), 3),
        "avg_citation_accuracy": round(float(summary.avg_citation_accuracy or 0), 3),
        "avg_hallucination": round(float(summary.avg_hallucination or 0), 3),
        "trends": trends,
    }


@router.get("/costs")
async def get_cost_analytics(
    days: int | None = Query(30, ge=1, le=365),
    date_from: str | None = None,
    date_to: str | None = None,
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start, end = _date_range(days, date_from, date_to)
    workspace_id = str(user.workspace_id)
    trunc = {"day": "day", "week": "week", "month": "month"}[granularity]

    sql = text("""
        SELECT
            date_trunc(:trunc, q.created_at) AS period,
            SUM(qr.cost_usd) AS total_cost,
            SUM(CAST(qr.token_usage->>'prompt_tokens' AS INTEGER)) AS prompt_tokens,
            SUM(CAST(qr.token_usage->>'completion_tokens' AS INTEGER)) AS completion_tokens,
            COUNT(*) AS query_count
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.cost_usd IS NOT NULL
        GROUP BY period
        ORDER BY period
    """)
    result = await db.execute(sql, {
        "trunc": trunc, "wid": workspace_id,
        "start": start, "end_dt": end,
    })
    breakdown = [
        {
            "period": row.period.isoformat(),
            "total_cost": round(float(row.total_cost or 0), 6),
            "prompt_tokens": row.prompt_tokens or 0,
            "completion_tokens": row.completion_tokens or 0,
            "query_count": row.query_count,
        }
        for row in result.fetchall()
    ]

    # Totals
    totals_sql = text("""
        SELECT
            SUM(qr.cost_usd) AS total_cost,
            SUM(CAST(qr.token_usage->>'prompt_tokens' AS INTEGER)) AS total_prompt_tokens,
            SUM(CAST(qr.token_usage->>'completion_tokens' AS INTEGER)) AS total_completion_tokens,
            AVG(qr.cost_usd) AS avg_cost_per_query
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.cost_usd IS NOT NULL
    """)
    totals = (await db.execute(totals_sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchone()

    return {
        "total_cost": round(float(totals.total_cost or 0), 6),
        "total_prompt_tokens": totals.total_prompt_tokens or 0,
        "total_completion_tokens": totals.total_completion_tokens or 0,
        "avg_cost_per_query": round(float(totals.avg_cost_per_query or 0), 6),
        "breakdown": breakdown,
    }


@router.get("/latency")
async def get_latency_analytics(
    days: int | None = Query(30, ge=1, le=365),
    date_from: str | None = None,
    date_to: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start, end = _date_range(days, date_from, date_to)
    workspace_id = str(user.workspace_id)

    # Percentiles
    sql = text("""
        SELECT
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY qr.latency_ms) AS p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY qr.latency_ms) AS p75,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY qr.latency_ms) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY qr.latency_ms) AS p99,
            AVG(qr.latency_ms) AS avg_latency,
            MIN(qr.latency_ms) AS min_latency,
            MAX(qr.latency_ms) AS max_latency,
            COUNT(*) AS count
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.latency_ms IS NOT NULL
    """)
    row = (await db.execute(sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchone()

    # Per-stage averages
    stage_sql = text("""
        SELECT
            AVG(CAST(qr.latency_breakdown->>'query_understanding_ms' AS FLOAT)) AS avg_query_understanding,
            AVG(CAST(qr.latency_breakdown->>'retrieval_ms' AS FLOAT)) AS avg_retrieval,
            AVG(CAST(qr.latency_breakdown->>'rerank_ms' AS FLOAT)) AS avg_rerank,
            AVG(CAST(qr.latency_breakdown->>'context_build_ms' AS FLOAT)) AS avg_context_build,
            AVG(CAST(qr.latency_breakdown->>'generation_ms' AS FLOAT)) AS avg_generation,
            AVG(CAST(qr.latency_breakdown->>'citation_validation_ms' AS FLOAT)) AS avg_citation_validation,
            AVG(CAST(qr.latency_breakdown->>'hallucination_check_ms' AS FLOAT)) AS avg_hallucination_check
        FROM query_results qr
        JOIN queries q ON q.id = qr.query_id
        WHERE q.workspace_id = CAST(:wid AS uuid)
          AND q.created_at >= :start
          AND q.created_at <= :end_dt
          AND qr.latency_ms IS NOT NULL
    """)
    stages = (await db.execute(stage_sql, {
        "wid": workspace_id, "start": start, "end_dt": end,
    })).fetchone()

    return {
        "p50": round(float(row.p50 or 0)),
        "p75": round(float(row.p75 or 0)),
        "p95": round(float(row.p95 or 0)),
        "p99": round(float(row.p99 or 0)),
        "avg_latency": round(float(row.avg_latency or 0)),
        "min_latency": round(float(row.min_latency or 0)) if row.min_latency else 0,
        "max_latency": round(float(row.max_latency or 0)) if row.max_latency else 0,
        "count": row.count or 0,
        "stage_breakdown": {
            "query_understanding": round(float(stages.avg_query_understanding or 0)),
            "retrieval": round(float(stages.avg_retrieval or 0)),
            "rerank": round(float(stages.avg_rerank or 0)),
            "context_build": round(float(stages.avg_context_build or 0)),
            "generation": round(float(stages.avg_generation or 0)),
            "citation_validation": round(float(stages.avg_citation_validation or 0)),
            "hallucination_check": round(float(stages.avg_hallucination_check or 0)),
        },
    }
