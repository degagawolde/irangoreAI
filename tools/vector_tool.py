"""Vector store and semantic search tools."""

from typing import List, Dict, Any, Optional
from core.logger import get_logger
from core.exceptions import VectorStoreException
from config import get_settings
from graph import get_graph
from llms import get_embeddings
from langchain_neo4j import Neo4jVector

logger = get_logger(__name__)


class VectorStoreTool:
    """Tool for vector-based semantic search using Neo4j."""

    _instance = None
    _vector_store = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize vector store."""
        if self._vector_store is None:
            self._initialize_vector_store()

    def _initialize_vector_store(self) -> None:
        """Initialize the Neo4j vector store."""
        try:

            settings = get_settings()
            graph = get_graph()
            embeddings = get_embeddings()

            logger.info(f"Initializing vector store with index: {settings.VECTOR_INDEX_NAME}")

            self._vector_store = Neo4jVector.from_existing_index(
                embeddings,
                graph=graph,
                index_name=settings.VECTOR_INDEX_NAME,
                node_label=settings.VECTOR_NODE_LABEL,
                text_node_property=settings.VECTOR_TEXT_PROPERTY,
                embedding_node_property=settings.VECTOR_EMBEDDING_PROPERTY,
                retrieval_query=self._get_default_retrieval_query(),
            )

            logger.info("Vector store initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {str(e)}")
            raise VectorStoreException(f"Failed to initialize vector store: {str(e)}")

    def _get_default_retrieval_query(self) -> str:
        """Get default retrieval query for vector store."""
        settings = get_settings()
        return f"""
RETURN
    node.{settings.VECTOR_TEXT_PROPERTY} AS text,
    score,
    {{
        node_id: id(node),
        properties: properties(node)
    }} AS metadata
"""

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        try:
            logger.debug(f"Vector search: {query} (k={k})")
            results = self._vector_store.similarity_search(query, k=k)
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            raise VectorStoreException(f"Vector search failed: {str(e)}")

    def search_with_score(
        self, query: str, k: int = 5
    ) -> List[tuple]:
        """Search with similarity scores."""
        try:
            logger.debug(f"Vector search with score: {query} (k={k})")
            results = self._vector_store.similarity_search_with_score(query, k=k)
            return results

        except Exception as e:
            logger.error(f"Vector search with score failed: {str(e)}")
            raise VectorStoreException(f"Vector search with score failed: {str(e)}")

    @property
    def vector_store(self):
        """Get the vector store instance."""
        return self._vector_store


def get_vector_store() -> VectorStoreTool:
    """Get vector store tool instance."""
    return VectorStoreTool()


def semantic_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Perform semantic search on documents."""
    vector_store = get_vector_store()
    return vector_store.search(query, k=k)
