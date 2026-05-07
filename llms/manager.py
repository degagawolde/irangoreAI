"""LLM (Language Model) management and initialization."""

from typing import Optional, Any
import requests
from core.logger import get_logger
from core.exceptions import LLMException
from config import get_settings

logger = get_logger(__name__)


class LLMManager:
    """Manages LLM initialization and lifecycle."""

    _instance: Optional["LLMManager"] = None
    _llm: Optional[Any] = None
    _embeddings: Optional[Any] = None

    def __new__(cls) -> "LLMManager":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize LLM manager."""
        if self._llm is None or self._embeddings is None:
            self._initialize_llm()

    def _initialize_llm(self) -> None:
        """Initialize LLM based on provider configuration."""
        try:
            settings = get_settings()
            logger.info(f"Initializing LLM with provider: {settings.LLM_PROVIDER}")

            if settings.LLM_PROVIDER.lower() == "ollama":
                self._initialize_ollama(settings)
            elif settings.LLM_PROVIDER.lower() == "openai":
                self._initialize_openai(settings)
            else:
                raise LLMException(f"Unknown LLM provider: {settings.LLM_PROVIDER}")

            logger.info("LLM initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise LLMException(f"Failed to initialize LLM: {str(e)}")

    def _initialize_ollama(self, settings) -> None:
        """Initialize Ollama LLM and embeddings."""
        try:
            from langchain_ollama import ChatOllama, OllamaEmbeddings
            self._validate_ollama(settings)

            self._llm = ChatOllama(
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                base_url=settings.OLLAMA_BASE_URL,
                client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
            )

            self._embeddings = OllamaEmbeddings(
                model=settings.EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
                client_kwargs={"timeout": settings.OLLAMA_TIMEOUT_SECONDS},
            )

            logger.info(
                f"Ollama LLM initialized: {settings.LLM_MODEL}, "
                f"Embeddings: {settings.EMBEDDING_MODEL}"
            )

        except ImportError as e:
            raise LLMException(f"Ollama dependencies not installed: {str(e)}")

    def _initialize_openai(self, settings) -> None:
        """Initialize OpenAI LLM and embeddings."""
        try:
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings

            if not settings.OPENAI_API_KEY:
                raise LLMException("OPENAI_API_KEY not set in environment")

            self._llm = ChatOpenAI(
                model=settings.OPENAI_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            )

            self._embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)

            logger.info(f"OpenAI LLM initialized: {settings.OPENAI_MODEL}")

        except ImportError as e:
            raise LLMException(f"OpenAI dependencies not installed: {str(e)}")

    def _validate_ollama(self, settings) -> None:
        """Fail fast if Ollama server or embedding model is unavailable."""
        tags_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        try:
            response = requests.get(tags_url, timeout=settings.OLLAMA_TIMEOUT_SECONDS)
            response.raise_for_status()
        except Exception as e:
            raise LLMException(
                "Ollama is not reachable. "
                f"base_url={settings.OLLAMA_BASE_URL} timeout={settings.OLLAMA_TIMEOUT_SECONDS}s error={str(e)}"
            ) from e

        try:
            payload = response.json()
            models = payload.get("models", [])
            names = {m.get("name") for m in models if isinstance(m, dict)}
        except Exception:
            names = set()

        expected = settings.EMBEDDING_MODEL
        expected_prefix = f"{expected}:"
        matched = any(name == expected or (isinstance(name, str) and name.startswith(expected_prefix)) for name in names)
        if not matched:
            logger.warning(
                "Embedding model not found in Ollama tags. model=%s available_models_count=%s",
                expected,
                len(names),
            )

    @property
    def llm(self) -> Any:
        """Get the LLM instance."""
        if self._llm is None:
            self._initialize_llm()
        return self._llm

    @property
    def embeddings(self) -> Any:
        """Get the embeddings instance."""
        if self._embeddings is None:
            self._initialize_llm()
        return self._embeddings


def get_llm_manager() -> LLMManager:
    """Get or create an LLM manager instance."""
    return LLMManager()


def get_llm() -> Any:
    """Convenience function to get the LLM instance."""
    return get_llm_manager().llm


def get_embeddings() -> Any:
    """Convenience function to get the embeddings instance."""
    return get_llm_manager().embeddings
