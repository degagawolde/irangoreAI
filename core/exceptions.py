"""Core exceptions for the application."""


class ChatbotException(Exception):
    """Base exception for the chatbot application."""

    pass


class LLMException(ChatbotException):
    """Exception raised for LLM-related errors."""

    pass


class GraphException(ChatbotException):
    """Exception raised for graph database errors."""

    pass


class SessionException(ChatbotException):
    """Exception raised for session management errors."""

    pass


class VectorStoreException(ChatbotException):
    """Exception raised for vector store errors."""

    pass


class AgentException(ChatbotException):
    """Exception raised for agent execution errors."""

    pass
