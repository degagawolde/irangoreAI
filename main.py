"""Main FastAPI application."""

from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from core import setup_logging, get_logger
from schemas import (
    ChatRequest,
    ChatResponse,
    SessionInfo,
    HealthResponse,
    ErrorResponse,
)
from sessions import get_session_manager
from agents import generate_response

from core.exceptions import (
    ChatbotException,
    SessionException,
    AgentException,
)

# Setup logging
setup_logging(log_level="INFO", log_format="standard")
logger = get_logger(__name__)

settings = get_settings()


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

        # Run agent via unified factory (agents/agent_factory.py)
        reply = generate_response(agent_prompt, session_id=request.session_id)

        # Add assistant message to session
        session_manager.add_message(request.session_id, "assistant", reply)

        messages = session_manager.get_messages(request.session_id)

        return ChatResponse(
            reply=reply,
            session_id=request.session_id,
            message_count=len(messages),
            sources=None,  # Can be populated if include_sources=True
            metadata={"model": settings.LLM_MODEL},
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
