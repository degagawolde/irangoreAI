from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    APP_NAME: str = "Citizen Regulation Assistant"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Provider switches
    LLM_PROVIDER: Literal["gemini", "ollama"] = "ollama"
    EMBED_PROVIDER: Literal["gemini", "ollama"] = "ollama"

    # OCR always uses Gemini — independent of LLM_PROVIDER
    OCR_PROVIDER: Literal["gemini"] = "gemini"

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_LLM_MODEL: str = "models/gemini-2.5-flash"
    GEMINI_EMBED_MODEL: str = "models/gemini-embedding-2"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "gpt-oss:20b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text:latest"

    # Elasticsearch
    ES_URL: str = "http://localhost:9200"
    ES_INDEX: str = "legal_documents"
    ES_VECTOR_DIMS: int = 768

    # Database
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()