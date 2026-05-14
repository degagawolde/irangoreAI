"""Internet search tools for agents."""

from __future__ import annotations

from typing import Any, Dict, List

import requests

from config import get_settings
from core.logger import get_logger

logger = get_logger(__name__)


def web_search(query: str, max_results: int = 5, timeout_seconds: int = 10) -> str:
    """Search the web using Serper Google Search API.

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
    settings = get_settings()
    api_key = getattr(settings, "SERPER_API_KEY", None)

    if not api_key:
        return "Web search failed: SERPER_API_KEY is not configured."

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json={
                "q": query,
                "num": max_results,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        logger.error(f"Web search failed for query='{query}': {exc}")
        return f"Web search failed: {exc}"

    lines: List[str] = [f"Web search results for: {query}"]
    organic = payload.get("organic", []) if isinstance(payload, dict) else []

    count = 0
    citations: List[str] = []
    for item in organic:
        if count >= max_results:
            break
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        link = str(item.get("link", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        if not (title or link or snippet):
            continue
        count += 1
        lines.append(f"[{count}] {title or 'Untitled'}")
        if snippet:
            lines.append(f"   Summary: {snippet} [source: {count}]")
        if link:
            lines.append(f"   URL: {link}")
            citations.append(f"[{count}] {link}")

    if count == 0:
        lines.append("No web results found.")
    else:
        lines.append("")
        lines.append(f"Citations (top {count}):")
        lines.extend(citations)

    return "\n".join(lines)
