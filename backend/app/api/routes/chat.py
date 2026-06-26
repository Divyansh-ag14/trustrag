import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.query import Query, QueryResult
from app.models.user import User
from app.models.workspace import Workspace
from app.rag.pipeline import process_query, process_query_stream
from app.schemas.chat import ChatRequest, ChatResponse, CitationDetail, SessionResponse

logger = structlog.get_logger()

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/query")
async def chat_query(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    workspace = await db.get(Workspace, user.workspace_id)
    workspace_name = workspace.name if workspace else "your organization"

    if request.session_id:
        session_id = request.session_id
    else:
        session_id = uuid.uuid4()

    result = await process_query(
        query=request.query,
        workspace_id=user.workspace_id,
        user_id=user.id,
        db=db,
        session_id=session_id,
        workspace_name=workspace_name,
    )

    citations = [
        CitationDetail(
            index=c["index"],
            document_title=c["document_title"],
            chunk_snippet=c["chunk_snippet"],
            document_id=uuid.UUID(c["document_id"]),
            relevance_score=c["relevance_score"],
        )
        for c in result.get("citations", [])
    ]

    return ChatResponse(
        query_id=result["query_id"],
        result_id=result["result_id"],
        answer=result["answer"],
        citations=citations,
        confidence_score=result["confidence_score"],
        verified=result.get("verified", False),
        faithfulness_score=result.get("faithfulness_score"),
        hallucination_score=result.get("hallucination_score"),
        citation_accuracy=result.get("citation_accuracy"),
        status=result["status"],
        has_conflicts=result.get("has_conflicts", False),
        follow_up_suggestions=result.get("follow_up_suggestions", []),
        retrieval_trace=result.get("retrieval_trace", {}),
        latency_breakdown=result.get("latency_breakdown", {}),
        token_usage=result.get("token_usage", {}),
        cost_usd=result.get("cost_usd"),
    )


@router.post("/query/stream")
async def chat_query_stream(
    request: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream the answer token-by-token through the FULL pipeline.

    Tokens stream as the answer generates; safety checks (citation validation +
    hallucination check) run AFTER and arrive in a final `verdict` event with the
    confidence/citations/status (and an `answer_override` if the answer was blocked).
    """
    workspace = await db.get(Workspace, user.workspace_id)
    workspace_name = workspace.name if workspace else "your organization"
    session_id = request.session_id or uuid.uuid4()

    async def event_stream():
        async for ev in process_query_stream(
            query=request.query,
            workspace_id=user.workspace_id,
            user_id=user.id,
            db=db,
            session_id=session_id,
            workspace_name=workspace_name,
        ):
            etype = ev["type"]
            if etype == "token":
                yield _sse_event("token", {"data": ev["data"]})
            elif etype == "verdict":
                yield _sse_event("verdict", ev["data"])
            elif etype == "error":
                yield _sse_event("error", {"detail": ev["data"]})
            elif etype == "done":
                yield _sse_event("done", {})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            Query.session_id,
            func.count(Query.id).label("query_count"),
            func.max(Query.created_at).label("last_query_at"),
        )
        .where(Query.user_id == user.id, Query.workspace_id == user.workspace_id)
        .group_by(Query.session_id)
        .order_by(desc("last_query_at"))
        .limit(50)
    )
    rows = result.all()

    return [
        SessionResponse(
            session_id=row.session_id,
            query_count=row.query_count,
            last_query_at=row.last_query_at.isoformat() if row.last_query_at else None,
        )
        for row in rows
        if row.session_id
    ]


@router.get("/sessions/{session_id}")
async def get_session_history(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Query)
        .where(
            Query.session_id == session_id,
            Query.user_id == user.id,
            Query.workspace_id == user.workspace_id,
        )
        .order_by(Query.created_at)
    )
    queries = result.scalars().all()

    if not queries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = []
    for q in queries:
        messages.append({"role": "user", "content": q.original_query, "timestamp": q.created_at.isoformat()})

        qr_result = await db.execute(
            select(QueryResult).where(QueryResult.query_id == q.id)
        )
        qr = qr_result.scalar_one_or_none()
        if qr:
            messages.append({
                "role": "assistant",
                "content": qr.answer,
                "confidence": qr.confidence_score,
                "citations": qr.citations,
                "status": qr.status,
                "timestamp": qr.created_at.isoformat(),
            })

    return {"session_id": session_id, "messages": messages}


def _sse_event(event_type: str, data) -> str:
    payload = json.dumps(data) if isinstance(data, (dict, list)) else json.dumps(data)
    return f"event: {event_type}\ndata: {payload}\n\n"
