"""Agent orchestration and routing logic."""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

from core.logger import get_logger
from llms import get_llm

logger = get_logger(__name__)

AUTO_AGENT_NAMES = {"auto", "orchestrator", "router"}


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
    if requested_agent and requested_agent not in AUTO_AGENT_NAMES:
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

