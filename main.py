"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime
import json
import time
import re
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core import setup_logging, get_logger
from core.runtime_services import (
    SimpleTTLCache,
    Metrics,
    score_source,
    detect_conflicts,
    scan_file_state,
)
from graph.observability import get_observability_store
from schemas import (
    ChatRequest,
    ChatResponse,
    Message,
    SessionInfo,
    HealthResponse,
    ErrorResponse,
)
from sessions import get_session_manager
from agents import generate_response, get_enabled_agents
from agents.orchestrator import plan_workflow
from tools.vector_tool import semantic_search

from core.exceptions import (
    ChatbotException,
    SessionException,
    AgentException,
)

# Setup logging
setup_logging(log_level="INFO", log_format="standard")
logger = get_logger(__name__)

settings = get_settings()
response_cache = SimpleTTLCache()
metrics = Metrics()
last_file_state: Dict[str, float] = {}

URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")


def build_sources(query: str, k: int = 5) -> List[dict]:
    """Build source entries from semantic search results."""
    try:
        results = semantic_search(query, k=k)
        sources: List[dict] = []

        for doc in results:
            metadata = getattr(doc, "metadata", {}) or {}
            properties = metadata.get("properties", {}) if isinstance(metadata, dict) else {}

            source_path = (
                metadata.get("source_path")
                or properties.get("source_path")
                or properties.get("source")
            )
            document_title = (
                metadata.get("document_title")
                or properties.get("document_title")
                or properties.get("title")
            )
            page_number = metadata.get("page_number") or properties.get("page_number")
            line_number = metadata.get("line_number") or properties.get("line_number")
            chunk_index = metadata.get("chunk_index") or properties.get("chunk_index")

            sources.append(
                {
                    "source": source_path,
                    "document": document_title,
                    "page": page_number,
                    "line": line_number,
                    "chunk_index": chunk_index,
                }
            )

        return sources
    except Exception as e:
        logger.warning(f"Failed to build sources: {str(e)}")
        return []


def format_agent_reply(raw_text: str) -> str:
    """Convert markdown-heavy LLM output into plain, readable text."""
    if not raw_text:
        return raw_text

    lines = raw_text.replace("\r\n", "\n").split("\n")
    cleaned_lines = []
    table_rows = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        # Skip markdown code fences
        if stripped.startswith("```"):
            continue

        # Collect markdown table rows for readable conversion
        if stripped.startswith("|") and stripped.endswith("|"):
            if not re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if cells:
                    table_rows.append(cells)
            continue

        # Convert headings and bullets to plain text
        text = re.sub(r"^#{1,6}\s*", "", stripped)
        text = re.sub(r"^[-*]\s+", "- ", text)
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"__(.*?)__", r"\1", text)
        cleaned_lines.append(text)

    # Convert markdown table to plain text section
    if len(table_rows) >= 2:
        cleaned_lines.append("")
        cleaned_lines.append("Key Differences:")
        headers = table_rows[0]
        for row in table_rows[1:]:
            if len(row) >= 3:
                cleaned_lines.append(f"- {headers[0]}: {row[0]}")
                cleaned_lines.append(f"  TBML: {row[1]}")
                cleaned_lines.append(f"  FIBML: {row[2]}")
            elif len(row) == 2:
                cleaned_lines.append(f"- {row[0]}: {row[1]}")

    # Normalize extra blank lines
    formatted = "\n".join(cleaned_lines)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted).strip()
    return formatted


def _extract_web_citations(text: str) -> List[str]:
    """Extract citation lines like '[1] https://...' or raw URLs."""
    if not text:
        return []

    urls: List[str] = []
    seen = set()

    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^\[(\d+)\]\s+(https?://\S+)$", stripped)
        if match:
            idx = match.group(1)
            url = match.group(2).rstrip(".,);")
            entry = f"[{idx}] {url}"
            if entry not in seen:
                seen.add(entry)
                urls.append(entry)

    if urls:
        return urls

    # Fallback: any URL
    for raw in URL_PATTERN.findall(text):
        url = raw.rstrip(".,);")
        entry = f"[{len(urls) + 1}] {url}"
        if entry not in seen:
            seen.add(entry)
            urls.append(entry)

    return urls


def _citations_to_sources(citations: List[str]) -> List[dict]:
    """Convert citation lines into structured source entries."""
    sources: List[dict] = []
    for item in citations:
        match = re.match(r"^\[(\d+)\]\s+(https?://\S+)$", item.strip())
        if match:
            sources.append(
                {
                    "source": match.group(2).rstrip(".,);"),
                    "document": f"web:{match.group(1)}",
                    "page": None,
                    "line": None,
                    "chunk_index": None,
                }
            )
        else:
            url_match = URL_PATTERN.search(item)
            if url_match:
                sources.append(
                    {
                        "source": url_match.group(0).rstrip(".,);"),
                        "document": "web",
                        "page": None,
                        "line": None,
                        "chunk_index": None,
                    }
                )
    return sources


def _score_sources(sources: List[dict]) -> List[dict]:
    """Attach trust/recency/confidence scores to sources."""
    scored = []
    for idx, src in enumerate(sources, start=1):
        url = src.get("source") or ""
        recency, trust = score_source(url, datetime.now())
        item = dict(src)
        item["id"] = item.get("id") or idx
        item["url"] = url
        item["retrieved_at"] = item.get("retrieved_at") or datetime.now().isoformat()
        item["recency_score"] = round(recency, 3)
        item["trust_score"] = round(trust, 3)
        item["confidence"] = round((recency + trust) / 2.0, 3)
        scored.append(item)
    return scored


def _ensure_sources_section(reply: str, citations: List[str]) -> str:
    """Ensure final reply includes explicit source links."""
    if not citations:
        return reply

    # If reply already contains URLs, keep as-is.
    if URL_PATTERN.search(reply):
        return reply

    # If Sources exists but has no URLs, append explicit link list.
    heading = "Source Links:" if re.search(r"(?im)^sources\s*:", reply) or re.search(r"(?im)^sources\s*$", reply) else "Sources:"
    sources_block = heading + "\n" + "\n".join(citations)
    return f"{reply}\n\n{sources_block}".strip()


def _run_agent_workflow(
    request: ChatRequest,
    agent_prompt: str,
    session_id: str,
    enabled_agents: List[str],
):
    """Run either a single routed agent or a multi-agent orchestrated workflow."""
    requested_agent = getattr(request, "agent_name", "auto")
    workflow_agents, workflow_reason = plan_workflow(
        query=request.message,
        requested_agent=requested_agent,
        enabled_agents=enabled_agents,
    )

    # Single-agent path
    if len(workflow_agents) == 1:
        selected_agent = workflow_agents[0]
        raw_reply = generate_response(
            agent_prompt,
            session_id=session_id,
            agent_name=selected_agent,
        )
        return raw_reply, selected_agent, workflow_reason, workflow_agents, [], [], []

    # Multi-agent path: run specialists (optionally in parallel), then synthesize.
    intermediate = []
    step_records = []
    workflow_citations: List[str] = []
    working_prompt = agent_prompt
    final_raw_reply = ""
    selected_agent = workflow_agents[-1]
    specialists = workflow_agents[:-1]
    synthesis_agent = workflow_agents[-1]

    if settings.ENABLE_PARALLEL_SPECIALISTS and len(specialists) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(specialists))) as executor:
            futures = {
                executor.submit(
                    generate_response,
                    working_prompt,
                    session_id=session_id,
                    agent_name=agent_name,
                ): agent_name
                for agent_name in specialists
            }
            for fut in as_completed(futures):
                agent_name = futures[fut]
                raw = fut.result()
                intermediate.append({"agent": agent_name, "output": raw})
                step_records.append({"agent": agent_name, "output": raw})
                workflow_citations.extend(_extract_web_citations(raw))
    else:
        for agent_name in specialists:
            raw = generate_response(
                working_prompt,
                session_id=session_id,
                agent_name=agent_name,
            )
            intermediate.append({"agent": agent_name, "output": raw})
            step_records.append({"agent": agent_name, "output": raw})
            workflow_citations.extend(_extract_web_citations(raw))

    synthesis_prompt = (
        f"Original user request:\n{request.message}\n\n"
        f"Specialist findings:\n{intermediate}\n\n"
        "Synthesize into one coherent answer with citations and uncertainty notes."
    )
    final_raw_reply = generate_response(
        synthesis_prompt,
        session_id=session_id,
        agent_name=synthesis_agent,
    )
    intermediate.append({"agent": synthesis_agent, "output": final_raw_reply})
    step_records.append({"agent": synthesis_agent, "output": final_raw_reply})
    workflow_citations.extend(_extract_web_citations(final_raw_reply))

    # Deduplicate citations while preserving order
    deduped = []
    seen = set()
    for c in workflow_citations:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return final_raw_reply, selected_agent, workflow_reason, workflow_agents, intermediate, deduped, step_records


# ==================== Lifespan Events ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting up chatbot backend...")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"Neo4j: {settings.NEO4J_URI}")

    yield

    # Shutdown
    logger.info("Shutting down chatbot backend...")
    session_manager = get_session_manager()
    session_manager.cleanup_expired_sessions()
    logger.info("Cleanup complete")


# ==================== Application Setup ====================
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


# ==================== Exception Handlers ====================
@app.exception_handler(SessionException)
async def session_exception_handler(request, exc):
    """Handle session exceptions."""
    logger.error(f"Session error: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error=str(exc),
            error_code="SESSION_ERROR",
            timestamp=datetime.now(),
        ).model_dump(),
    )


@app.exception_handler(AgentException)
async def agent_exception_handler(request, exc):
    """Handle agent exceptions."""
    logger.error(f"Agent error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            error_code="AGENT_ERROR",
            timestamp=datetime.now(),
        ).model_dump(),
    )


@app.exception_handler(ChatbotException)
async def chatbot_exception_handler(request, exc):
    """Handle chatbot exceptions."""
    logger.error(f"Chatbot error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            error_code="CHATBOT_ERROR",
            timestamp=datetime.now(),
        ).model_dump(),
    )


# ==================== Health Check ====================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        services_status = {
            "llm": "ok",
            "graph": "ok",
            "session_manager": "ok",
        }

        return HealthResponse(
            status="healthy",
            version=settings.API_VERSION,
            timestamp=datetime.now(),
            services=services_status,
        )

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


# ==================== Chat Endpoints ====================
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint using agentic AI with Graph RAG."""
    try:
        started = time.perf_counter()
        metrics.inc("requests_total")
        cache_key = json.dumps(
            {"m": request.message, "a": request.agent_name, "o": request.output_mode},
            sort_keys=True,
        )
        cached = response_cache.get(cache_key)
        if cached is not None:
            metrics.inc("cache_hits")
            return cached
        metrics.inc("cache_misses")

        # Get or create session
        session_manager = get_session_manager()
        obs = get_observability_store()

        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                request.session_id = session_manager.create_session()
        else:
            request.session_id = session_manager.create_session()

        # Add user message to session
        session_manager.add_message(request.session_id, "user", request.message)
        logger.info(f"User message in session {request.session_id}: {request.message}")

        # Get conversation context
        context_messages = session_manager.get_messages(
            request.session_id, limit=settings.MAX_HISTORY_LENGTH
        )

        # Prepare agent prompt with context
        context_str = "\n".join(
            [f"{m['role']}: {m['content']}" for m in context_messages[:-1]]
        )
       
        agent_prompt = (
            f"Previous conversation:\n{context_str}\n\nCurrent question: {request.message}"
            if context_str
            else request.message
        )

        # Run agent or multi-agent orchestration workflow
        enabled_agents = get_enabled_agents()
        trace_id = obs.create_trace(
            session_id=request.session_id,
            request_message=request.message,
            requested_agent=getattr(request, "agent_name", None),
        )
        raw_reply, selected_agent, routing_reason, workflow_agents, intermediate_outputs, workflow_citations, step_records = _run_agent_workflow(
            request=request,
            agent_prompt=agent_prompt,
            session_id=request.session_id,
            enabled_agents=enabled_agents,
        )
        for idx, step in enumerate(step_records, start=1):
            try:
                obs.add_trace_step(trace_id, step["agent"], str(step["output"]), idx)
            except Exception:
                pass
        try:
            obs.finish_trace(trace_id, selected_agent, workflow_agents, status="ok")
        except Exception:
            pass
        reply = format_agent_reply(raw_reply)
        reply = _ensure_sources_section(reply, workflow_citations)

        # Add assistant message to session
        session_manager.add_message(request.session_id, "assistant", reply)

        messages = session_manager.get_messages(request.session_id)

        sources = build_sources(request.message) if request.include_sources else None
        web_sources = _citations_to_sources(workflow_citations)
        if web_sources:
            sources = (sources or []) + web_sources
        sources = _score_sources(sources or [])

        conflicts = detect_conflicts(reply)
        if conflicts:
            reply = (
                f"{reply}\n\nConflicts Detected:\n"
                + "\n".join([f"- {c['claim_a']}  <>  {c['claim_b']}" for c in conflicts])
            )

        if request.output_mode == "decision":
            avg_conf = round(
                sum([s.get("confidence", 0.6) for s in sources]) / max(len(sources), 1),
                3,
            )
            reply = json.dumps(
                {
                    "answer": reply,
                    "confidence": avg_conf,
                    "assumptions": ["Source trust and recency heuristics were applied."],
                    "missing_data": [] if sources else ["No sources were retrieved."],
                    "next_best_actions": [
                        "Add more targeted source constraints",
                        "Cross-verify with additional trusted sources",
                    ],
                },
                ensure_ascii=True,
            )

        response = ChatResponse(
            reply=reply,
            session_id=request.session_id,
            message_count=len(messages),
            sources=sources,
            metadata={
                "model": settings.LLM_MODEL,
                "selected_agent": selected_agent,
                "routing_reason": routing_reason,
                "requested_agent": getattr(request, "agent_name", None),
                "workflow_agents": workflow_agents,
                "intermediate_steps": len(intermediate_outputs),
                "web_citations_count": len(workflow_citations),
                "conflicts_count": len(conflicts),
                "output_mode": request.output_mode,
                "trace_id": trace_id,
            },
        )
        metrics.observe_latency((time.perf_counter() - started) * 1000.0)
        metrics.inc_agent(selected_agent)
        response_cache.set(cache_key, response, settings.RESPONSE_CACHE_TTL_SECONDS)
        return response

    except SessionException as e:
        logger.error(f"Session error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except AgentException as e:
        logger.error(f"Agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ==================== Chat History Management Endpoints ====================
@app.get("/history/{session_id}", response_model=List[Message])
async def get_history(session_id: str):
    """Get chat history."""
    try:
        session_manager = get_session_manager()
        messages = session_manager.get_messages(
            session_id, limit=settings.MAX_HISTORY_LENGTH
        )

        return messages

    except SessionException as e:
        logger.error(f"History error: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get history")


# ==================== Session Management Endpoints ====================
@app.post("/sessions")
async def create_session():
    """Create a new session."""
    try:
        session_manager = get_session_manager()
        session_id = session_manager.create_session()

        return {"session_id": session_id, "created_at": datetime.now()}

    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """Get session information."""
    try:
        session_manager = get_session_manager()
        info = session_manager.get_session_info(session_id)

        if not info:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionInfo(**info)

    except SessionException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get session")


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        session_manager = get_session_manager()
        session_manager.delete_session(session_id)

        return {"status": "deleted", "session_id": session_id}

    except Exception as e:
        logger.error(f"Failed to delete session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    try:
        session_manager = get_session_manager()
        sessions = session_manager.get_all_sessions_info()

        return {
            "total": len(sessions),
            "sessions": sessions,
        }

    except Exception as e:
        logger.error(f"Failed to list sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list sessions")


# ==================== Agent Management Endpoints ====================
@app.get("/agents")
async def list_agents():
    """List all available agents and their capabilities."""
    try:
        agents = get_enabled_agents()
        return {
            "total": len(agents),
            "agents": agents,
            "default_agent": "auto",
            "info": "Use agent_name=auto (or orchestrator) to enable query-based agent routing"
        }
    except Exception as e:
        logger.error(f"Failed to list agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@app.get("/metrics")
async def get_metrics():
    """Runtime observability metrics."""
    snap = metrics.snapshot()
    metric_id = None
    try:
        metric_id = get_observability_store().save_metrics_snapshot(snap)
    except Exception:
        pass
    return {"metric_id": metric_id, **snap}


@app.get("/metrics/snapshots")
async def get_metrics_snapshots(limit: int = 50):
    """Get persisted metric snapshots from Neo4j."""
    try:
        rows = get_observability_store().list_metric_snapshots(limit=limit)
        return {"total": len(rows), "items": rows}
    except Exception as e:
        logger.error(f"Failed to load metric snapshots: {e}")
        raise HTTPException(status_code=500, detail="Failed to load metric snapshots")


@app.get("/traces")
async def list_traces(limit: int = 50):
    """List recent traces."""
    try:
        traces = get_observability_store().list_traces(limit=limit)
        return {"total": len(traces), "items": traces}
    except Exception as e:
        logger.error(f"Failed to list traces: {e}")
        raise HTTPException(status_code=500, detail="Failed to list traces")


@app.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get one trace with its steps/tool calls."""
    try:
        trace = get_observability_store().get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trace: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trace")


@app.get("/sessions/{session_id}/graph")
async def get_session_graph(session_id: str):
    """Get persisted session graph (session + messages + traces)."""
    try:
        data = get_observability_store().get_session_graph(session_id)
        if not data:
            raise HTTPException(status_code=404, detail="Session not found in graph")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session graph: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session graph")


@app.get("/dashboard/summary")
async def dashboard_summary():
    """Single-call dashboard summary for observability UI."""
    try:
        return get_observability_store().dashboard_summary()
    except Exception as e:
        logger.error(f"Failed to build dashboard summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to build dashboard summary")


@app.post("/refresh-index")
async def refresh_index():
    """Check incremental file changes for refresh workflows."""
    global last_file_state
    current = scan_file_state(settings.FILE_DATA_ROOT)
    changed = [p for p, ts in current.items() if last_file_state.get(p) != ts]
    removed = [p for p in last_file_state.keys() if p not in current]
    last_file_state = current
    return {
        "changed_count": len(changed),
        "removed_count": len(removed),
        "changed_files": changed[:200],
        "removed_files": removed[:200],
    }


# ==================== Root Endpoint ====================
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "title": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        log_level="info",
    )
