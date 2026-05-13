"""Relational database tools for agentic workflows."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from config import get_settings
from core.logger import get_logger
from .result_contract import make_tool_result

logger = get_logger(__name__)

_ENGINE: Engine | None = None


def _get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        settings = get_settings()
        db_url = getattr(settings, "SQL_DATABASE_URL", None)
        if not db_url:
            raise ValueError("SQL_DATABASE_URL is not configured")
        _ENGINE = create_engine(db_url, future=True)
    return _ENGINE


def sql_list_tables() -> str:
    """List available SQL tables."""
    try:
        engine = _get_engine()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return make_tool_result(
            source="sql",
            status="ok",
            summary=f"Discovered {len(tables)} tables",
            evidence=[{"table": t} for t in tables],
            confidence=0.95,
        )
    except Exception as exc:
        logger.error(f"sql_list_tables failed: {exc}")
        return make_tool_result(
            source="sql",
            status="error",
            summary=f"Failed to list tables: {exc}",
            confidence=0.0,
        )


def sql_describe_table(table_name: str) -> str:
    """Describe columns for one SQL table."""
    try:
        engine = _get_engine()
        inspector = inspect(engine)
        columns = inspector.get_columns(table_name)
        evidence: List[Dict[str, Any]] = []
        for col in columns:
            evidence.append(
                {
                    "name": col.get("name"),
                    "type": str(col.get("type")),
                    "nullable": bool(col.get("nullable", True)),
                }
            )
        return make_tool_result(
            source="sql",
            status="ok",
            summary=f"Described table '{table_name}' with {len(evidence)} columns",
            evidence=evidence,
            confidence=0.95,
        )
    except Exception as exc:
        logger.error(f"sql_describe_table failed: {exc}")
        return make_tool_result(
            source="sql",
            status="error",
            summary=f"Failed to describe table '{table_name}': {exc}",
            confidence=0.0,
        )


def sql_query(query: str, limit: int = 50) -> str:
    """Execute read-only SQL query (SELECT/CTE only)."""
    q = (query or "").strip()
    if not q:
        return make_tool_result(
            source="sql",
            status="error",
            summary="Empty SQL query",
            confidence=0.0,
        )

    normalized = q.lower().lstrip()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        return make_tool_result(
            source="sql",
            status="error",
            summary="Only read-only SELECT/WITH queries are allowed",
            confidence=0.0,
        )

    safe_limit = max(1, min(int(limit), 200))
    wrapped = f"SELECT * FROM ({q}) AS subq LIMIT {safe_limit}"
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            rows = conn.execute(text(wrapped))
            items = [dict(r._mapping) for r in rows]
        return make_tool_result(
            source="sql",
            status="ok",
            summary=f"Query executed successfully with {len(items)} rows",
            evidence=items,
            confidence=0.9,
            raw_ref="sql_query",
            metadata={"limit": safe_limit},
        )
    except Exception as exc:
        logger.error(f"sql_query failed: {exc}")
        return make_tool_result(
            source="sql",
            status="error",
            summary=f"SQL query failed: {exc}",
            confidence=0.0,
        )

