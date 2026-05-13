"""Data models and schemas for the API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class Message(BaseModel):
    """Represents a single message."""

    role: str = Field(..., description="Role of the message sender (user, assistant)")
    content: str = Field(..., description="Content of the message")
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.now, description="Timestamp of the message"
    )


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(
        default=None, description="Session ID (create new if not provided)"
    )
    include_sources: bool = Field(
        default=False, description="Include source documents in response"
    )
    agent_name: Optional[str] = Field(
        default="auto", description="Agent to use: auto/orchestrator, chat, vector, cypher, full, scoped, deep_search, graph_agent, sql_agent, web_agent, darkintel_agent, file_agent, synthesis_agent"
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    reply: str = Field(..., description="Assistant reply")
    session_id: str = Field(..., description="Session ID")
    message_count: int = Field(..., description="Total messages in session")
    sources: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Source documents used for the response"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )

class SessionInfo(BaseModel):
    """Session information."""

    session_id: str = Field(..., description="Session ID")
    created_at: datetime = Field(..., description="Session creation time")
    last_accessed: datetime = Field(..., description="Last access time")
    message_count: int = Field(..., description="Number of messages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")
class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Response timestamp")
    services: Dict[str, str] = Field(..., description="Status of each service")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    timestamp: datetime = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")
