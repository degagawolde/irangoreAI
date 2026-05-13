"""Agent orchestration and routing logic."""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple

from core.logger import get_logger
from llms import get_llm

logger = get_logger(__name__)

AUTO_AGENT_NAMES = {
    "auto",
    "orchestrator",
    "orchastrator",
    "orchestrator_agent",
    "router",
}

SPECIALIST_AGENT_MAP: Dict[str, str] = {
    "graph": "graph_agent",
    "sql": "sql_agent",
    "web": "web_agent",
    "darkintel": "darkintel_agent",
    "files": "file_agent",
    "synthesis": "synthesis_agent",
}


def _heuristic_route(query: str, enabled_agents: List[str]) -> str:
    """Deterministic fallback router when LLM routing fails."""
    text = (query or "").lower()
    available = set(enabled_agents)

    if any(k in text for k in ["latest", "today", "current", "news", "web", "internet", "search online"]):
        if "deep_search" in available:
            return "deep_search"

    if any(k in text for k in ["relationship", "graph", "cypher", "connected", "between"]):
        if "cypher" in available:
            return "cypher"

    if any(k in text for k in ["semantic", "similar", "find in docs", "context search"]):
        if "vector" in available:
            return "vector"

    if "cypher" in available:
        return "cypher"
    return enabled_agents[0] if enabled_agents else "cypher"


def route_agent(
    query: str,
    requested_agent: Optional[str],
    enabled_agents: List[str],
) -> Tuple[str, str]:
    """Choose which agent should handle a user query.

    Returns:
        Tuple of (agent_name, reason)
    """
    normalized_requested = (requested_agent or "").strip().lower()

    if normalized_requested and normalized_requested not in AUTO_AGENT_NAMES:
        return requested_agent, "explicitly selected by user"

    if not enabled_agents:
        return "cypher", "fallback: no enabled agents list available"

    llm = get_llm()
    prompt = (
        "You are an agent router. Choose exactly one best agent for the user query.\n"
        f"Available agents: {', '.join(enabled_agents)}\n"
        "Routing guidance:\n"
        "- deep_search: internet/public web + internal documents\n"
        "- cypher: structured/relationship/document-fact questions\n"
        "- vector: semantic document retrieval\n"
        "- chat/scoped/full: use only when clearly better than above\n"
        "Return ONLY strict JSON: "
        '{"agent":"<name>","reason":"<short reason>"}\n'
        f"User query: {query}"
    )

    try:
        result = llm.invoke(prompt)
        content = getattr(result, "content", result)
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        text = str(content).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        payload = json.loads(text)
        chosen = str(payload.get("agent", "")).strip()
        reason = str(payload.get("reason", "")).strip() or "chosen by orchestrator"

        if chosen in enabled_agents:
            return chosen, reason

        fallback = _heuristic_route(query, enabled_agents)
        return fallback, f"llm suggested unknown agent '{chosen}', fallback used"
    except Exception as exc:
        fallback = _heuristic_route(query, enabled_agents)
        logger.warning(f"LLM router failed, using fallback agent '{fallback}': {exc}")
        return fallback, f"fallback routing used ({exc})"


def plan_workflow(
    query: str,
    requested_agent: Optional[str],
    enabled_agents: List[str],
) -> Tuple[List[str], str]:
    """Plan a multi-agent workflow.

    Returns:
        (workflow_agents, reason)
    """
    normalized_requested = (requested_agent or "").strip().lower()
    if normalized_requested and normalized_requested not in AUTO_AGENT_NAMES:
        return [requested_agent], "explicitly selected by user"

    available = set(enabled_agents)
    plan: List[str] = []
    text = (query or "").lower()

    if any(k in text for k in ["graph", "relationship", "connected", "path", "neo4j"]):
        if "graph_agent" in available:
            plan.append("graph_agent")

    if any(k in text for k in ["sql", "table", "database", "postgres", "mysql", "query"]):
        if "sql_agent" in available:
            plan.append("sql_agent")

    if any(k in text for k in ["web", "internet", "latest", "news", "current"]):
        if "web_agent" in available:
            plan.append("web_agent")

    if any(k in text for k in ["dark web", "threat", "ioc", "leak", "breach", "tor"]):
        if "darkintel_agent" in available:
            plan.append("darkintel_agent")

    if any(k in text for k in ["csv", "excel", "xlsx", "markdown", ".md", ".txt", "file"]):
        if "file_agent" in available:
            plan.append("file_agent")

    if not plan:
        single, reason = route_agent(query=query, requested_agent="auto", enabled_agents=enabled_agents)
        plan = [single]
        if "synthesis_agent" in available and single != "synthesis_agent":
            plan.append("synthesis_agent")
        return plan, f"fallback single-agent route used: {reason}"

    if "synthesis_agent" in available and "synthesis_agent" not in plan:
        plan.append("synthesis_agent")

    return plan, "planned multi-agent workflow from query intent"
