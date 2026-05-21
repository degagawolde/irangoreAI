import json
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, desc
from app.api.v1.schemas.regulation import RegulationQueryRequest, RegulationQueryResponse
from app.api.v1.services.regulation_service import answer_regulation_query
from app.api.dependencies import DBSession
from app.models.query_log import QueryLog

router = APIRouter(prefix="/regulations", tags=["Regulations"])


@router.post("/ask", response_model=RegulationQueryResponse)
async def ask_regulation(request: RegulationQueryRequest, db: DBSession):
    """Ask a legal question in any language."""
    try:
        return await answer_regulation_query(
            question=request.question,
            jurisdiction=request.jurisdiction,
            db=db
        )
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