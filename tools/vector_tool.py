"""Vector store and semantic search tools."""

from typing import List, Dict, Any, Optional
from core.logger import get_logger
from core.exceptions import VectorStoreException
from config import get_settings
from graph import get_graph
from llms import get_embeddings
from langchain_neo4j import Neo4jVector
from langchain_core.documents import Document

logger = get_logger(__name__)


class VectorStoreTool:
    """Tool for vector-based semantic search using Neo4j with modern SEARCH API."""

    _instance = None
    _vector_store = None
    _graph = None
    _embeddings = None

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
        """Initialize the Neo4j vector store with modern metadata extraction."""
        try:
            settings = get_settings()
            self._graph = get_graph()
            self._embeddings = get_embeddings()

            logger.info(f"Initializing vector store with index: {settings.VECTOR_INDEX_NAME}")

            # Use modern retrieval query with elementId() and minimal property access
            retrieval_query = self._get_modern_retrieval_query()

            self._vector_store = Neo4jVector.from_existing_index(
                self._embeddings,
                graph=self._graph,
                index_name=settings.VECTOR_INDEX_NAME,
                node_label=settings.VECTOR_NODE_LABEL,
                text_node_property=settings.VECTOR_TEXT_PROPERTY,
                embedding_node_property=settings.VECTOR_EMBEDDING_PROPERTY,
                retrieval_query=retrieval_query,
            )

            logger.info("Vector store initialized successfully with modern Neo4j API")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {str(e)}")
            raise VectorStoreException(f"Failed to initialize vector store: {str(e)}")

    def _get_modern_retrieval_query(self) -> str:
        """Get retrieval query using modern Neo4j elementId() instead of deprecated id().
        
        Uses elementId(node) which is the recommended replacement for the deprecated id().
        Only returns properties that are guaranteed to exist across all nodes.
        All optional/dynamic properties are accessible via the properties() function.
        
        Note: LangChain's Neo4jVector still uses db.index.vector.queryNodes internally.
        This will be replaced with the newer SEARCH syntax in future Neo4j driver updates.
        """
        settings = get_settings()
        return f"""
RETURN
    node.{settings.VECTOR_TEXT_PROPERTY} AS text,
    score,
    {{
        element_id: elementId(node),
        all_properties: properties(node)
    }} AS metadata
"""

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents using vector similarity.
        
        Args:
            query: Text query to search for
            k: Number of results to return
            
        Returns:
            List of Document objects with similarity results
        """
        try:
            logger.debug(f"Vector search: {query} (k={k})")
            results = self._vector_store.similarity_search(query, k=k)
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            raise VectorStoreException(f"Vector search failed: {str(e)}")

    def search_with_score(self, query: str, k: int = 5) -> List[tuple]:
        """Search with similarity scores.
        
        Args:
            query: Text query to search for
            k: Number of results to return
            
        Returns:
            List of (Document, score) tuples
        """
        try:
            logger.debug(f"Vector search with score: {query} (k={k})")
            results = self._vector_store.similarity_search_with_score(query, k=k)
            return results

        except Exception as e:
            logger.error(f"Vector search with score failed: {str(e)}")
            raise VectorStoreException(f"Vector search with score failed: {str(e)}")

    def search_with_custom_cypher(
        self, embedding_query: str, cypher_suffix: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Advanced: Search using custom Cypher suffix for complex filtering.
        
        Args:
            embedding_query: Text to embed for search
            cypher_suffix: Custom Cypher code appended after score filtering
            k: Number of results to return
            
        Returns:
            Raw query results
            
        Example:
            cypher_suffix = 'WHERE node.language = "en" RETURN node.text AS text, score'
        """
        try:
            settings = get_settings()
            # Get embedding vector
            query_vector = self._embeddings.embed_query(embedding_query)
            
            cypher_query = f"""
            CALL db.index.vector.queryNodes('{settings.VECTOR_INDEX_NAME}', {k}, $query_vector)
            YIELD node, score
            {cypher_suffix}
            """
            
            logger.debug(f"Custom vector search with Cypher suffix")
            results = self._graph.query(cypher_query, {"query_vector": query_vector})
            return results
            
        except Exception as e:
            logger.error(f"Custom vector search failed: {str(e)}")
            raise VectorStoreException(f"Custom vector search failed: {str(e)}")

    @property
    def vector_store(self):
        """Get the vector store instance."""
        return self._vector_store


def get_vector_store() -> VectorStoreTool:
    """Get vector store tool instance."""
    return VectorStoreTool()


def semantic_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Perform semantic search on documents.
    
    Args:
        query: Text query
        k: Number of results
        
    Returns:
        List of search results
    """
    vector_store = get_vector_store()
    return vector_store.search(query, k=k)
