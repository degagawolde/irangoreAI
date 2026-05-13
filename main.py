"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime
import re
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core import setup_logging, get_logger
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
        return raw_reply, selected_agent, workflow_reason, workflow_agents, []

    # Multi-agent path: run specialists sequentially, synthesize at the end.
    intermediate = []
    working_prompt = agent_prompt
    final_raw_reply = ""
    selected_agent = workflow_agents[-1]

    for idx, agent_name in enumerate(workflow_agents):
        raw = generate_response(
            working_prompt,
            session_id=session_id,
            agent_name=agent_name,
        )
        intermediate.append({"agent": agent_name, "output": raw})
        if idx < len(workflow_agents) - 1:
            working_prompt = (
                f"Original user request:\n{request.message}\n\n"
                f"Intermediate findings so far:\n{intermediate}\n\n"
                "Continue your specialist analysis and return concise, evidence-grounded findings."
            )
        else:
            final_raw_reply = raw

    return final_raw_reply, selected_agent, workflow_reason, workflow_agents, intermediate


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
        # Get or create session
        session_manager = get_session_manager()

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
        raw_reply, selected_agent, routing_reason, workflow_agents, intermediate_outputs = _run_agent_workflow(
            request=request,
            agent_prompt=agent_prompt,
            session_id=request.session_id,
            enabled_agents=enabled_agents,
        )
        reply = format_agent_reply(raw_reply)

        # Add assistant message to session
        session_manager.add_message(request.session_id, "assistant", reply)

        messages = session_manager.get_messages(request.session_id)

        sources = build_sources(request.message) if request.include_sources else None

        return ChatResponse(
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
            },
        )

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
