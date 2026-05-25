from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlalchemy import select, desc
from app.api.v1.schemas.regulation import (
    RegulationQueryRequest,
    RegulationQueryResponse
)
from app.api.v1.services.regulation_service import answer_regulation_query
from app.api.dependencies import DBSession
from app.models.query_log import QueryLog
import json

router = APIRouter(prefix="/regulations", tags=["Regulations"])


async def _save_query_log(
    db,
    question: str,
    jurisdiction: str,
    answer: str,
    sources: list
):
    """Runs after response is sent. User never waits for this."""
    try:
        log = QueryLog(
            question=question,
            jurisdiction=jurisdiction,
            answer=answer,
            sources=json.dumps([s.model_dump() for s in sources])
        )
        db.add(log)
        await db.commit()
        print(f"[BG] Query logged to database")
    except Exception as e:
        print(f"[BG] Failed to log query: {e}")


@router.post("/ask", response_model=RegulationQueryResponse)
async def ask_regulation(
    request: RegulationQueryRequest,
    background_tasks: BackgroundTasks,   # ← injected by FastAPI
    db: DBSession,
):
    """Ask a legal question in any language."""
    try:
        # User waits for this
        result = await answer_regulation_query(
            question=request.question,
            jurisdiction=request.jurisdiction
        )

        # User does NOT wait for this
        background_tasks.add_task(
            _save_query_log,
            db=db,
            question=request.question,
            jurisdiction=request.jurisdiction,
            answer=result.answer,
            sources=result.sources
        )

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_query_history(db: DBSession, limit: int = 20):
    """Return the last N questions asked."""
    result = await db.execute(
        select(QueryLog)
        .order_by(desc(QueryLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id":           log.id,
            "question":     log.question,
            "jurisdiction": log.jurisdiction,
            "sources":      json.loads(log.sources) if log.sources else [],
            "created_at":   log.created_at,
        }
        for log in logs
    ]