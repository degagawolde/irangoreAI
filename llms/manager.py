"""LLM (Language Model) management and initialization."""

from typing import Optional, Any
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

            self._llm = ChatOllama(
                model=settings.LLM_MODEL,
                temperature=settings.LLM_TEMPERATURE,
                base_url=settings.OLLAMA_BASE_URL,
            )

            self._embeddings = OllamaEmbeddings(
                model=settings.EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL,
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
