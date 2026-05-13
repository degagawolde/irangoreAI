"""Synthesis helpers for multi-agent outputs."""

from __future__ import annotations

from typing import Optional

from .result_contract import make_tool_result


def package_findings(question: str, findings: str, context: Optional[str] = None) -> str:
    """Package intermediate findings into a normalized payload."""
    summary = f"Packaged findings for question: {question[:120]}"
    evidence = [{"question": question, "findings": findings, "context": context or ""}]
    return make_tool_result(
        source="synthesis",
        status="ok",
        summary=summary,
        evidence=evidence,
        confidence=0.8,
    )

