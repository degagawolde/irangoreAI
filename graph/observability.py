"""Neo4j persistence for sessions, traces, tool calls, and metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.logger import get_logger
from graph import get_graph

logger = get_logger(__name__)


class ObservabilityStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._graph = get_graph()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        queries = [
            "CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.session_id IS UNIQUE",
            "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
            "CREATE CONSTRAINT trace_id_unique IF NOT EXISTS FOR (t:Trace) REQUIRE t.trace_id IS UNIQUE",
            "CREATE CONSTRAINT toolcall_id_unique IF NOT EXISTS FOR (tc:ToolCall) REQUIRE tc.toolcall_id IS UNIQUE",
            "CREATE CONSTRAINT metric_id_unique IF NOT EXISTS FOR (ms:MetricSnapshot) REQUIRE ms.metric_id IS UNIQUE",
        ]
        for q in queries:
            try:
                self._graph.query(q)
            except Exception as exc:
                logger.debug(f"Observability schema setup skipped: {exc}")

    def upsert_session(self, session_id: str, created_at: Optional[str] = None) -> None:
        now = created_at or datetime.now().isoformat()
        self._graph.query(
            """
            MERGE (s:Session {session_id: $session_id})
            ON CREATE SET s.created_at = $created_at
            SET s.last_accessed = $created_at
            """,
            {"session_id": session_id, "created_at": now},
        )

    def add_message(self, session_id: str, role: str, content: str, timestamp: Optional[str] = None) -> str:
        message_id = str(uuid4())
        ts = timestamp or datetime.now().isoformat()
        self._graph.query(
            """
            MERGE (s:Session {session_id: $session_id})
            ON CREATE SET s.created_at = $timestamp
            SET s.last_accessed = $timestamp
            CREATE (m:Message {message_id: $message_id, role: $role, content: $content, timestamp: $timestamp})
            MERGE (s)-[:HAS_MESSAGE]->(m)
            """,
            {
                "session_id": session_id,
                "message_id": message_id,
                "role": role,
                "content": content,
                "timestamp": ts,
            },
        )
        # Preserve QA lineage: link assistant response to the latest user query
        # in the same session when possible.
        if role == "assistant":
            self._graph.query(
                """
                MATCH (s:Session {session_id: $session_id})-[:HAS_MESSAGE]->(a:Message {message_id: $assistant_id})
                MATCH (s)-[:HAS_MESSAGE]->(u:Message {role: 'user'})
                WHERE u.timestamp <= $timestamp
                WITH a, u
                ORDER BY u.timestamp DESC
                LIMIT 1
                MERGE (a)-[r:RESPONDS_TO]->(u)
                ON CREATE SET r.created_at = $timestamp
                """,
                {
                    "session_id": session_id,
                    "assistant_id": message_id,
                    "timestamp": ts,
                },
            )
        return message_id

    def create_trace(self, session_id: str, request_message: str, requested_agent: Optional[str]) -> str:
        trace_id = str(uuid4())
        now = datetime.now().isoformat()
        self._graph.query(
            """
            MERGE (s:Session {session_id: $session_id})
            ON CREATE SET s.created_at = $now
            SET s.last_accessed = $now
            CREATE (t:Trace {
              trace_id: $trace_id,
              request_message: $request_message,
              requested_agent: $requested_agent,
              started_at: $now
            })
            MERGE (s)-[:HAS_TRACE]->(t)
            """,
            {
                "session_id": session_id,
                "trace_id": trace_id,
                "request_message": request_message,
                "requested_agent": requested_agent,
                "now": now,
            },
        )
        return trace_id

    def add_trace_step(self, trace_id: str, agent_name: str, output: str, step_index: int) -> None:
        toolcall_id = str(uuid4())
        self._graph.query(
            """
            MATCH (t:Trace {trace_id: $trace_id})
            CREATE (tc:ToolCall {
              toolcall_id: $toolcall_id,
              tool_name: $agent_name,
              output: $output,
              step_index: $step_index,
              timestamp: $timestamp
            })
            MERGE (t)-[:USED_TOOL]->(tc)
            """,
            {
                "trace_id": trace_id,
                "toolcall_id": toolcall_id,
                "agent_name": agent_name,
                "output": output,
                "step_index": step_index,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def finish_trace(self, trace_id: str, selected_agent: str, workflow_agents: List[str], status: str = "ok") -> None:
        self._graph.query(
            """
            MATCH (t:Trace {trace_id: $trace_id})
            SET t.selected_agent = $selected_agent,
                t.workflow_agents = $workflow_agents,
                t.status = $status,
                t.finished_at = $finished_at
            """,
            {
                "trace_id": trace_id,
                "selected_agent": selected_agent,
                "workflow_agents": workflow_agents,
                "status": status,
                "finished_at": datetime.now().isoformat(),
            },
        )

    def save_metrics_snapshot(self, metrics: Dict[str, Any]) -> str:
        metric_id = str(uuid4())
        self._graph.query(
            """
            CREATE (ms:MetricSnapshot {
              metric_id: $metric_id,
              timestamp: $timestamp,
              payload: $payload
            })
            """,
            {
                "metric_id": metric_id,
                "timestamp": datetime.now().isoformat(),
                "payload": metrics,
            },
        )
        return metric_id

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        rows = self._graph.query(
            """
            MATCH (t:Trace {trace_id: $trace_id})
            OPTIONAL MATCH (t)-[:USED_TOOL]->(tc:ToolCall)
            RETURN t as trace, tc
            ORDER BY tc.step_index ASC
            """,
            {"trace_id": trace_id},
        )
        if not rows:
            return None
        trace_props = dict(rows[0]["trace"]) if rows[0].get("trace") else {}
        steps = []
        for row in rows:
            tc = row.get("tc")
            if tc:
                steps.append(dict(tc))
        return {"trace": trace_props, "steps": steps}

    def list_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._graph.query(
            """
            MATCH (t:Trace)
            RETURN t
            ORDER BY t.started_at DESC
            LIMIT $limit
            """,
            {"limit": max(1, min(int(limit), 500))},
        )
        return [dict(r["t"]) for r in rows if r.get("t")]

    def get_session_graph(self, session_id: str) -> Optional[Dict[str, Any]]:
        rows = self._graph.query(
            """
            MATCH (s:Session {session_id: $session_id})
            OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
            OPTIONAL MATCH (s)-[:HAS_TRACE]->(t:Trace)
            RETURN s, collect(DISTINCT m) as messages, collect(DISTINCT t) as traces
            """,
            {"session_id": session_id},
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "session": dict(row["s"]) if row.get("s") else {},
            "messages": [dict(m) for m in (row.get("messages") or []) if m],
            "traces": [dict(t) for t in (row.get("traces") or []) if t],
        }

    def list_metric_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = self._graph.query(
            """
            MATCH (m:MetricSnapshot)
            RETURN m
            ORDER BY m.timestamp DESC
            LIMIT $limit
            """,
            {"limit": max(1, min(int(limit), 500))},
        )
        return [dict(r["m"]) for r in rows if r.get("m")]

    def dashboard_summary(self) -> Dict[str, Any]:
        sessions = self._graph.query("MATCH (s:Session) RETURN count(s) as c")
        traces = self._graph.query("MATCH (t:Trace) RETURN count(t) as c")
        traces_24h = self._graph.query(
            """
            MATCH (t:Trace)
            WHERE datetime(t.started_at) >= datetime() - duration('P1D')
            RETURN count(t) as c
            """
        )
        top_agents = self._graph.query(
            """
            MATCH (t:Trace)
            WHERE t.selected_agent IS NOT NULL
            RETURN t.selected_agent as agent, count(*) as c
            ORDER BY c DESC
            LIMIT 10
            """
        )
        latest_metrics = self._graph.query(
            """
            MATCH (m:MetricSnapshot)
            RETURN m
            ORDER BY m.timestamp DESC
            LIMIT 1
            """
        )
        latest_payload = {}
        if latest_metrics and latest_metrics[0].get("m"):
            latest_payload = dict(latest_metrics[0]["m"]).get("payload", {}) or {}
        return {
            "sessions_total": int((sessions[0].get("c") if sessions else 0) or 0),
            "traces_total": int((traces[0].get("c") if traces else 0) or 0),
            "traces_last_24h": int((traces_24h[0].get("c") if traces_24h else 0) or 0),
            "top_agents": [{"agent": r.get("agent"), "count": r.get("c")} for r in top_agents],
            "latest_runtime_metrics": latest_payload,
        }


def get_observability_store() -> ObservabilityStore:
    return ObservabilityStore()
