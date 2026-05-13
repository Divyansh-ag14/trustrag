from pydantic import BaseModel


class UsageStats(BaseModel):
    total_queries: int
    unique_users: int
    queries_by_date: list[dict]


class QualityStats(BaseModel):
    avg_confidence: float
    avg_faithfulness: float | None
    avg_citation_accuracy: float | None
    avg_hallucination_rate: float | None
    quality_by_date: list[dict]


class CostStats(BaseModel):
    total_cost_usd: float
    cost_by_date: list[dict]
    cost_by_component: dict


class LatencyStats(BaseModel):
    p50_ms: float
    p75_ms: float
    p95_ms: float
    avg_breakdown: dict
