"""Vector store and semantic search tools using Neo4j vector indexes."""

from typing import List, Dict, Any, Optional, Tuple

from core.logger import get_logger
from core.exceptions import VectorStoreException
from config import get_settings
from graph import get_graph
from llms import get_embeddings

from langchain_core.documents import Document

logger = get_logger(__name__)


class VectorStoreTool:
    """
    Tool for vector-based semantic search using Neo4j vector indexes.

    Uses:
        CALL db.index.vector.queryNodes(...)

    Compatible with Neo4j 5.x production deployments.
    """

    _instance = None
    _graph = None
    _embeddings = None
    _settings = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._graph is None:
            self._initialize()

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------

    def _initialize(self) -> None:
        """Initialize graph, embeddings, and validate vector index."""
        try:
            self._settings = get_settings()
            self._graph = get_graph()
            self._embeddings = get_embeddings()

            self._verify_vector_index()

            logger.info(
                "Vector store initialized successfully "
                f"(index={self._settings.VECTOR_INDEX_NAME}, "
                f"label={self._settings.VECTOR_NODE_LABEL})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise VectorStoreException(
                f"Failed to initialize vector store: {e}"
            )

    def _verify_vector_index(self) -> None:
        """Verify that the configured vector index exists."""

        try:
            query = """
            SHOW INDEXES
            YIELD
                name,
                type,
                labelsOrTypes,
                properties

            WHERE
                name = $index_name
                AND type = 'VECTOR'

            RETURN
                name,
                labelsOrTypes,
                properties
            """

            result = self._graph.query(
                query,
                {
                    "index_name": self._settings.VECTOR_INDEX_NAME
                },
            )

            if not result:
                raise VectorStoreException(
                    f"Vector index '{self._settings.VECTOR_INDEX_NAME}' "
                    f"does not exist."
                )

            index_info = result[0]

            actual_label = (
                index_info["labelsOrTypes"][0]
                if index_info["labelsOrTypes"]
                else None
            )

            actual_property = (
                index_info["properties"][0]
                if index_info["properties"]
                else None
            )

            if actual_label != self._settings.VECTOR_NODE_LABEL:
                logger.warning(
                    "Vector index label mismatch: "
                    f"expected={self._settings.VECTOR_NODE_LABEL}, "
                    f"actual={actual_label}"
                )

            if actual_property != self._settings.VECTOR_EMBEDDING_PROPERTY:
                logger.warning(
                    "Vector embedding property mismatch: "
                    f"expected={self._settings.VECTOR_EMBEDDING_PROPERTY}, "
                    f"actual={actual_property}"
                )

            logger.info(
                f"Verified vector index: {self._settings.VECTOR_INDEX_NAME}"
            )

        except Exception as e:
            logger.error(f"Vector index verification failed: {e}")
            raise VectorStoreException(
                f"Vector index verification failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Embeddings
    # -------------------------------------------------------------------------

    def _embed_query(self, text: str) -> List[float]:
        """Generate embedding vector for query text."""

        if not text or not text.strip():
            raise VectorStoreException(
                "Cannot embed empty query text."
            )

        try:
            return self._embeddings.embed_query(text)

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise VectorStoreException(
                f"Embedding generation failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def _clean_metadata(
        self,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Remove large/sensitive fields from metadata.
        """

        if not metadata:
            return {}

        cleaned = dict(metadata)

        # Remove embedding vectors
        cleaned.pop(
            self._settings.VECTOR_EMBEDDING_PROPERTY,
            None,
        )

        # Remove any accidental embedding-like properties
        keys_to_remove = []

        for key in cleaned.keys():
            if "embedding" in key.lower():
                keys_to_remove.append(key)

        for key in keys_to_remove:
            cleaned.pop(key, None)

        return cleaned

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 5,
    ) -> List[Document]:
        """
        Semantic vector similarity search.

        Returns:
            List[Document]
        """

        try:
            logger.debug(
                f"Vector search query='{query}' k={k}"
            )

            query_vector = self._embed_query(query)

            cypher = f"""
            CALL db.index.vector.queryNodes(
                $index_name,
                $k,
                $query_vector
            )

            YIELD node, score

            RETURN
                node.{self._settings.VECTOR_TEXT_PROPERTY} AS text,
                score,
                elementId(node) AS element_id,
                properties(node) AS metadata

            ORDER BY score DESC
            """

            results = self._graph.query(
                cypher,
                {
                    "index_name": self._settings.VECTOR_INDEX_NAME,
                    "query_vector": query_vector,
                    "k": k,
                },
            )

            documents = []

            for record in results:
                metadata = self._clean_metadata(
                    record.get("metadata", {})
                )

                document = Document(
                    page_content=record.get("text", ""),
                    metadata={
                        "score": record.get("score"),
                        "element_id": record.get("element_id"),
                        **metadata,
                    },
                )

                documents.append(document)

            return documents

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise VectorStoreException(
                f"Vector search failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Search With Scores
    # -------------------------------------------------------------------------

    def search_with_score(
        self,
        query: str,
        k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """
        Semantic vector search returning (Document, score).
        """

        try:
            documents = self.search(query=query, k=k)

            results = []

            for doc in documents:
                score = float(doc.metadata.get("score", 0.0))
                results.append((doc, score))

            return results

        except Exception as e:
            logger.error(f"Vector search with score failed: {e}")
            raise VectorStoreException(
                f"Vector search with score failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Custom Cypher Search
    # -------------------------------------------------------------------------

    def search_with_custom_cypher(
        self,
        embedding_query: str,
        cypher_suffix: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Advanced vector search with custom Cypher suffix.

        Example:
            MATCH (d:Document)-[:HAS_CHUNK]->(node)
            RETURN d.title, node.text, score
            ORDER BY score DESC
            LIMIT 5
        """

        try:
            logger.debug(
                "Custom vector search "
                f"(query={embedding_query}, k={k})"
            )

            query_vector = self._embed_query(
                embedding_query
            )

            cypher = f"""
            CALL db.index.vector.queryNodes(
                $index_name,
                $k,
                $query_vector
            )

            YIELD node, score

            {cypher_suffix}
            """

            results = self._graph.query(
                cypher,
                {
                    "index_name": self._settings.VECTOR_INDEX_NAME,
                    "query_vector": query_vector,
                    "k": k,
                },
            )

            cleaned_results = []

            for record in results:
                cleaned_record = {}

                for key, value in record.items():

                    # Remove huge embedding arrays
                    if (
                        isinstance(value, list)
                        and len(value) > 100
                        and all(
                            isinstance(v, (float, int))
                            for v in value[:10]
                        )
                    ):
                        continue

                    cleaned_record[key] = value

                cleaned_results.append(cleaned_record)

            return cleaned_results

        except Exception as e:
            logger.error(
                f"Custom vector search failed: {e}"
            )

            raise VectorStoreException(
                f"Custom vector search failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Raw Query
    # -------------------------------------------------------------------------

    def raw_vector_query(
        self,
        query_vector: List[float],
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Execute raw vector query directly from vector.
        """

        try:
            cypher = """
            CALL db.index.vector.queryNodes(
                $index_name,
                $k,
                $query_vector
            )

            YIELD node, score

            RETURN node, score
            ORDER BY score DESC
            """

            return self._graph.query(
                cypher,
                {
                    "index_name": self._settings.VECTOR_INDEX_NAME,
                    "query_vector": query_vector,
                    "k": k,
                },
            )

        except Exception as e:
            logger.error(f"Raw vector query failed: {e}")

            raise VectorStoreException(
                f"Raw vector query failed: {e}"
            )

    # -------------------------------------------------------------------------
    # Deprecated Compatibility
    # -------------------------------------------------------------------------

    @property
    def vector_store(self):
        logger.warning(
            "'vector_store' property is deprecated. "
            "Use search() instead."
        )
        return None


# -----------------------------------------------------------------------------
# Public Interface
# -----------------------------------------------------------------------------

def get_vector_store() -> VectorStoreTool:
    """Get singleton vector store instance."""
    return VectorStoreTool()


def semantic_search(
    query: str,
    k: int = 5,
) -> List[Document]:
    """
    Convenience semantic search function.
    """

    vector_store = get_vector_store()

    return vector_store.search(
        query=query,
        k=k,
    )