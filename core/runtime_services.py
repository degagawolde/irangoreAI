"""Runtime services: cache, metrics, source scoring, conflict detection, refresh state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
import re


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime


class SimpleTTLCache:
    def __init__(self) -> None:
        self._data: Dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        now = datetime.now()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            if entry.expires_at < now:
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        with self._lock:
            self._data[key] = CacheEntry(
                value=value, expires_at=datetime.now() + timedelta(seconds=max(1, ttl_seconds))
            )


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.counters: Dict[str, int] = {
            "requests_total": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "tool_failures": 0,
        }
        self.agent_counts: Dict[str, int] = {}
        self.latency_ms: List[float] = []

    def inc(self, key: str, value: int = 1) -> None:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + value

    def observe_latency(self, ms: float) -> None:
        with self._lock:
            self.latency_ms.append(ms)
            if len(self.latency_ms) > 1000:
                self.latency_ms = self.latency_ms[-1000:]

    def inc_agent(self, agent: str) -> None:
        with self._lock:
            self.agent_counts[agent] = self.agent_counts.get(agent, 0) + 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            avg = (sum(self.latency_ms) / len(self.latency_ms)) if self.latency_ms else 0.0
            return {
                "counters": dict(self.counters),
                "agent_counts": dict(self.agent_counts),
                "latency_avg_ms": round(avg, 2),
                "latency_samples": len(self.latency_ms),
            }


TRUST_WEIGHTS = {
    "reuters.com": 0.95,
    "ieee.org": 0.92,
    "nature.com": 0.92,
    "arxiv.org": 0.85,
    "wikipedia.org": 0.7,
    "youtube.com": 0.5,
}


def score_source(url: str, retrieved_at: datetime) -> Tuple[float, float]:
    domain_score = 0.6
    for domain, score in TRUST_WEIGHTS.items():
        if domain in url:
            domain_score = score
            break
    age_days = max(0, (datetime.now() - retrieved_at).days)
    recency_score = max(0.3, 1.0 - min(age_days, 365) / 365.0)
    return recency_score, domain_score


def detect_conflicts(text: str) -> List[Dict[str, str]]:
    """Naive conflict detector for contradictory numeric/date claims."""
    claims = re.findall(r"([A-Z][^.:\n]{5,120}(?:\d{4}|nm|%)[^.:\n]{0,80})", text or "")
    normalized = {}
    conflicts: List[Dict[str, str]] = []
    for c in claims:
        key = re.sub(r"\d+", "#", c.lower())
        if key in normalized and normalized[key] != c:
            conflicts.append({"claim_a": normalized[key], "claim_b": c})
        else:
            normalized[key] = c
    return conflicts[:10]


def scan_file_state(root_path: str) -> Dict[str, float]:
    root = Path(root_path).expanduser()
    state: Dict[str, float] = {}
    if not root.exists():
        return state
    for p in root.rglob("*"):
        if p.is_file():
            state[str(p)] = p.stat().st_mtime
    return state

