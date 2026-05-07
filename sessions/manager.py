"""Session management for chat conversations."""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from core.logger import get_logger
from core.exceptions import SessionException
from config import get_settings

logger = get_logger(__name__)


class ChatSession:
    """Represents a single chat session."""

    def __init__(self, session_id: str):
        """Initialize a chat session."""
        self.session_id = session_id
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.messages: List[Dict[str, str]] = []
        self.metadata: Dict[str, Any] = {}

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        self.last_accessed = datetime.now()

    def get_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get messages from the session."""
        if limit:
            return self.messages[-limit:]
        return self.messages

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if session has expired."""
        elapsed = (datetime.now() - self.last_accessed).total_seconds()
        return elapsed > timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "message_count": len(self.messages),
            "metadata": self.metadata,
        }


class SessionManager:
    """Manages chat sessions."""

    _instance = None
    _sessions: Dict[str, ChatSession] = {}

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_session(self, session_id: Optional[str] = None) -> str:
        """Create a new chat session."""
        try:
            session_id = session_id or str(uuid.uuid4())
            self._sessions[session_id] = ChatSession(session_id)
            logger.info(f"Created session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session: {str(e)}")
            raise SessionException(f"Failed to create session: {str(e)}")

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID."""
        session = self._sessions.get(session_id)

        if session:
            settings = get_settings()
            if session.is_expired(settings.SESSION_TIMEOUT):
                logger.info(f"Session expired: {session_id}")
                del self._sessions[session_id]
                return None

            session.last_accessed = datetime.now()
            return session

        return None

    def add_message(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Add a message to a session."""
        try:
            session = self.get_session(session_id)
            if not session:
                raise SessionException(f"Session not found: {session_id}")

            session.add_message(role, content)
            logger.debug(f"Added {role} message to session: {session_id}")

        except SessionException:
            raise
        except Exception as e:
            logger.error(f"Failed to add message: {str(e)}")
            raise SessionException(f"Failed to add message: {str(e)}")

    def get_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get messages from a session."""
        try:
            session = self.get_session(session_id)
            if not session:
                raise SessionException(f"Session not found: {session_id}")

            return session.get_messages(limit)

        except SessionException:
            raise
        except Exception as e:
            logger.error(f"Failed to get messages: {str(e)}")
            raise SessionException(f"Failed to get messages: {str(e)}")

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        try:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Deleted session: {session_id}")

        except Exception as e:
            logger.error(f"Failed to delete session: {str(e)}")
            raise SessionException(f"Failed to delete session: {str(e)}")

    def cleanup_expired_sessions(self) -> None:
        """Remove expired sessions."""
        try:
            settings = get_settings()
            expired_sessions = [
                sid
                for sid, session in self._sessions.items()
                if session.is_expired(settings.SESSION_TIMEOUT)
            ]

            for sid in expired_sessions:
                del self._sessions[sid]
                logger.info(f"Cleaned up expired session: {sid}")

            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")

    def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """Get session information."""
        session = self.get_session(session_id)
        if not session:
            raise SessionException(f"Session not found: {session_id}")

        return session.to_dict()

    def get_all_sessions_info(self) -> List[Dict[str, Any]]:
        """Get information about all active sessions."""
        return [session.to_dict() for session in self._sessions.values()]


def get_session_manager() -> SessionManager:
    """Get session manager instance."""
    return SessionManager()
