"""Configuration management for the chatbot backend."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    API_TITLE: str = "Chatbot Backend - Graph RAG with Agentic AI"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "A production-ready chatbot backend using agentic AI and graph RAG"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = DEBUG

    # Neo4j Configuration
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # LLM Configuration
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen3:8b")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # ollama, openai, etc.
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "qwen3-embedding")

    # Ollama Configuration
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    EMBEDDING_BATCH_SIZE: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
    PDF_OCR_FALLBACK_ENABLED: bool = os.getenv("PDF_OCR_FALLBACK_ENABLED", "true").lower() == "true"
    PDF_OCR_LANG: str = os.getenv("PDF_OCR_LANG", "eng")

    # OpenAI Configuration (optional)
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")

    # Vector Store Configuration
    VECTOR_INDEX_NAME: str = os.getenv("VECTOR_INDEX_NAME", "documentChunks")
    VECTOR_NODE_LABEL: str = os.getenv("VECTOR_NODE_LABEL", "Chunk")
    VECTOR_TEXT_PROPERTY: str = os.getenv("VECTOR_TEXT_PROPERTY", "text")
    VECTOR_EMBEDDING_PROPERTY: str = os.getenv("VECTOR_EMBEDDING_PROPERTY", "embedding")

    # Session Configuration
    SESSION_TIMEOUT: int = 3600  # 1 hour in seconds
    MAX_HISTORY_LENGTH: int = 50  # Max messages to keep in history

    # Multi-source connectors
    SQL_DATABASE_URL: Optional[str] = os.getenv("SQL_DATABASE_URL")
    FILE_DATA_ROOT: str = os.getenv("FILE_DATA_ROOT", "./_files")
    SERPER_API_KEY: Optional[str] = os.getenv("SERPER_API_KEY")
    DARKINTEL_API_URL: Optional[str] = os.getenv("DARKINTEL_API_URL")
    DARKINTEL_API_KEY: Optional[str] = os.getenv("DARKINTEL_API_KEY")
    RESPONSE_CACHE_TTL_SECONDS: int = int(os.getenv("RESPONSE_CACHE_TTL_SECONDS", "600"))
    ENABLE_PARALLEL_SPECIALISTS: bool = os.getenv("ENABLE_PARALLEL_SPECIALISTS", "true").lower() == "true"

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "json"  # json or standard

    # CORS Configuration
    CORS_ORIGINS: list = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["*"]
    CORS_ALLOW_HEADERS: list = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra environment variables not defined in Settings


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
