"""Shared tool result contract for multi-source agents."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def make_tool_result(
    source: str,
    status: str,
    summary: str,
    evidence: Optional[List[Dict[str, Any]]] = None,
    confidence: float = 0.5,
    raw_ref: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a normalized tool result payload as JSON string."""
    payload = {
        "source": source,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "confidence": max(0.0, min(float(confidence), 1.0)),
        "evidence": evidence or [],
        "raw_ref": raw_ref,
        "metadata": metadata or {},
    }
    return json.dumps(payload, ensure_ascii=True)

