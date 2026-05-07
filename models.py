"""
Backward compatibility models.
For new code, use schemas.py instead.
"""

from schemas import *  # noqa: F401, F403

__all__ = [
    "Message",
    "ChatRequest",
    "ChatResponse",
    "SessionInfo",
    "HealthResponse",
    "ErrorResponse",
]