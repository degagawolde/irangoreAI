"""File intelligence tools for CSV, Excel, Markdown, and text."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from core.logger import get_logger
from .result_contract import make_tool_result

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".md", ".txt"}


def list_data_files(root_path: str = "./_files") -> str:
    """List supported files under the target directory."""
    try:
        root = Path(root_path).expanduser().resolve()
        if not root.exists():
            return make_tool_result(
                source="files",
                status="error",
                summary=f"Path does not exist: {root}",
                confidence=0.0,
            )

        files = [
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        evidence = [{"path": str(p), "type": p.suffix.lower()} for p in files]
        return make_tool_result(
            source="files",
            status="ok",
            summary=f"Found {len(files)} supported files",
            evidence=evidence,
            confidence=0.95,
            raw_ref=str(root),
        )
    except Exception as exc:
        logger.error(f"list_data_files failed: {exc}")
        return make_tool_result(
            source="files",
            status="error",
            summary=f"Failed to list files: {exc}",
            confidence=0.0,
        )


def file_search(query: str, root_path: str = "./_files", max_hits: int = 20) -> str:
    """Search text content in .csv/.md/.txt files.

    Note: .xlsx files are listed via `list_data_files` but are not text-searched
    unless converted externally or parser dependencies are added.
    """
    term = (query or "").strip().lower()
    if not term:
        return make_tool_result(
            source="files",
            status="error",
            summary="No query provided for file search",
            confidence=0.0,
        )

    root = Path(root_path).expanduser().resolve()
    if not root.exists():
        return make_tool_result(
            source="files",
            status="error",
            summary=f"Path does not exist: {root}",
            confidence=0.0,
        )

    hits: List[Dict[str, str]] = []
    limit = max(1, min(int(max_hits), 200))

    for path in root.rglob("*"):
        if len(hits) >= limit:
            break
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".csv", ".md", ".txt"}:
            continue

        try:
            if suffix == ".csv":
                with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                    reader = csv.reader(f)
                    for idx, row in enumerate(reader, start=1):
                        row_text = ", ".join(row)
                        if term in row_text.lower():
                            hits.append(
                                {"path": str(path), "line": str(idx), "snippet": row_text[:400]}
                            )
                            if len(hits) >= limit:
                                break
            else:
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    for idx, line in enumerate(f, start=1):
                        if term in line.lower():
                            hits.append(
                                {"path": str(path), "line": str(idx), "snippet": line.strip()[:400]}
                            )
                            if len(hits) >= limit:
                                break
        except Exception as exc:
            logger.warning(f"Failed scanning file {path}: {exc}")

    status = "ok" if hits else "empty"
    summary = f"Found {len(hits)} matches for '{query}'"
    return make_tool_result(
        source="files",
        status=status,
        summary=summary,
        evidence=hits,
        confidence=0.85 if hits else 0.4,
        raw_ref=str(root),
    )

