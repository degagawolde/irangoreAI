"""Lightweight evaluation harness for multi-agent responses."""

from __future__ import annotations

import json
from typing import List, Dict, Any

from agents import generate_response
from agents.orchestrator import plan_workflow
from agents import get_enabled_agents


TEST_CASES: List[Dict[str, Any]] = [
    {"q": "Find latest AI chip updates and list sources", "expect_sources": True},
    {"q": "Use graph relationships between documents and summarize", "expect_sources": False},
]


def run_eval() -> Dict[str, Any]:
    enabled = get_enabled_agents()
    results = []
    passed = 0
    for case in TEST_CASES:
        plan, _ = plan_workflow(case["q"], "auto", enabled)
        agent = plan[-1] if plan else "cypher"
        reply = generate_response(case["q"], agent_name=agent)
        has_sources = "http" in str(reply).lower() or "sources" in str(reply).lower()
        ok = (has_sources if case["expect_sources"] else True)
        passed += 1 if ok else 0
        results.append({"question": case["q"], "agent": agent, "ok": ok})
    return {"total": len(TEST_CASES), "passed": passed, "results": results}


if __name__ == "__main__":
    print(json.dumps(run_eval(), ensure_ascii=True, indent=2))

