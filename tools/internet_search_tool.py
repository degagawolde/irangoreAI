"""Internet search tools for agents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from core.logger import get_logger

logger = get_logger(__name__)


def _safe_get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    """Safely read nested keys from dict-like payloads."""
    current: Any = d
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current if current is not None else default


def web_search(query: str, max_results: int = 5, timeout_seconds: int = 10) -> str:
    """Search the web using DuckDuckGo instant answer + related topics.

    Args:
        query: User query to search for.
        max_results: Max number of items to return.
        timeout_seconds: HTTP timeout in seconds.

    Returns:
        Formatted search results as text for agent consumption.
    """
    query = (query or "").strip()
    if not query:
        return "No query provided."

    max_results = max(1, min(int(max_results), 10))
    timeout_seconds = max(3, min(int(timeout_seconds), 30))

    try:
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.error(f"Web search failed for query='{query}': {exc}")
        return f"Web search failed: {exc}"

    lines: List[str] = [f"Web search results for: {query}"]

    abstract = _safe_get(payload, ["AbstractText"], "")
    abstract_url = _safe_get(payload, ["AbstractURL"], "")
    heading = _safe_get(payload, ["Heading"], "")

    if abstract:
        title = heading or "Top Result"
        lines.append(f"1. {title}")
        lines.append(f"   Summary: {abstract}")
        if abstract_url:
            lines.append(f"   URL: {abstract_url}")

    related = _safe_get(payload, ["RelatedTopics"], []) or []
    count = 1 if abstract else 0

    def _append_topic(topic: Dict[str, Any]) -> bool:
        nonlocal count
        if count >= max_results:
            return False
        text = topic.get("Text")
        url = topic.get("FirstURL")
        if text and url:
            count += 1
            lines.append(f"{count}. {text}")
            lines.append(f"   URL: {url}")
            return True
        return False

    for item in related:
        if count >= max_results:
            break
        if isinstance(item, dict) and "Topics" in item:
            for sub in item.get("Topics", []):
                if count >= max_results:
                    break
                if isinstance(sub, dict):
                    _append_topic(sub)
        elif isinstance(item, dict):
            _append_topic(item)

    if count == 0:
        answer = _safe_get(payload, ["Answer"], "") or _safe_get(payload, ["Definition"], "")
        if answer:
            lines.append(f"1. {answer}")
            count = 1

    if count == 0:
        lines.append("No web results found.")

    return "\n".join(lines)

