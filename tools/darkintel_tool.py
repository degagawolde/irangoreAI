"""Dark web intelligence adapter tools.

These tools provide a safe integration point for external dark-intel platforms.
"""

from __future__ import annotations

from typing import Dict, List

import requests

from config import get_settings
from core.logger import get_logger
from .result_contract import make_tool_result

logger = get_logger(__name__)


def darkintel_search(query: str, max_results: int = 10, timeout_seconds: int = 15) -> str:
    """Query configured dark-intel provider endpoint.

    Expected endpoint contract:
    POST <DARKINTEL_API_URL>
    Authorization: Bearer <DARKINTEL_API_KEY>
    JSON body: {"query": "...", "max_results": 10}
    """
    settings = get_settings()
    api_url = getattr(settings, "DARKINTEL_API_URL", None)
    api_key = getattr(settings, "DARKINTEL_API_KEY", None)

    if not api_url or not api_key:
        return make_tool_result(
            source="darkintel",
            status="not_configured",
            summary="Dark intelligence connector is not configured",
            confidence=0.0,
            metadata={
                "required_env": ["DARKINTEL_API_URL", "DARKINTEL_API_KEY"],
            },
        )

    payload = {"query": query, "max_results": max(1, min(int(max_results), 50))}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=max(5, min(int(timeout_seconds), 60)))
        res.raise_for_status()
        data = res.json()
        items = data.get("results", []) if isinstance(data, dict) else []
        evidence: List[Dict[str, str]] = []
        for item in items:
            if isinstance(item, dict):
                evidence.append(
                    {
                        "title": str(item.get("title", "")),
                        "snippet": str(item.get("snippet", "")),
                        "reference": str(item.get("reference", "")),
                        "risk_level": str(item.get("risk_level", "")),
                    }
                )
        return make_tool_result(
            source="darkintel",
            status="ok",
            summary=f"Retrieved {len(evidence)} dark-intel results",
            evidence=evidence,
            confidence=0.75 if evidence else 0.4,
            raw_ref=api_url,
        )
    except Exception as exc:
        logger.error(f"darkintel_search failed: {exc}")
        return make_tool_result(
            source="darkintel",
            status="error",
            summary=f"Dark intelligence search failed: {exc}",
            confidence=0.0,
            raw_ref=api_url,
        )

