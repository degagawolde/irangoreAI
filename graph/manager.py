"""Graph database connection and management."""

from typing import Optional, Any
from core.logger import get_logger
from core.exceptions import GraphException
from config import get_settings

logger = get_logger(__name__)


class GraphManager:
    """Manages Neo4j graph connections and queries."""

    _instance: Optional["GraphManager"] = None
    _graph: Optional[Any] = None

    def __new__(cls) -> "GraphManager":
        """Singleton pattern to ensure only one graph instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize graph manager with settings."""
        if self._graph is None:
            self._connect()

    def _connect(self) -> None:
        """Connect to Neo4j database."""
        try:
            from langchain_neo4j import Neo4jGraph
            
            settings = get_settings()
            logger.info(f"Connecting to Neo4j at {settings.NEO4J_URI}")

            self._graph = Neo4jGraph(
                url=settings.NEO4J_URI,
                username=settings.NEO4J_USERNAME,
                password=settings.NEO4J_PASSWORD,
                database=settings.NEO4J_DATABASE,
            )

            # Test connection
            result = self._graph.query("RETURN 'Connection Successful' AS status")
            logger.info(f"Neo4j connection successful: {result}")

        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise GraphException(f"Failed to connect to Neo4j: {str(e)}")

    @property
    def graph(self) -> Any:
        """Get the graph instance."""
        if self._graph is None:
            self._connect()
        return self._graph

    def query(self, cypher_query: str, **params) -> list:
        """Execute a Cypher query."""
        try:
            logger.debug(f"Executing query: {cypher_query}")
            result = self._graph.query(cypher_query, **params)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise GraphException(f"Query execution failed: {str(e)}")

    def get_schema(self) -> str:
        """Get the graph schema."""
        try:
            return self._graph.get_schema()
        except Exception as e:
            logger.error(f"Failed to get schema: {str(e)}")
            raise GraphException(f"Failed to get schema: {str(e)}")

    def close(self) -> None:
        """Close the graph connection."""
        try:
            if self._graph:
                logger.info("Closing Neo4j connection")
                # Neo4j driver typically auto-closes, but we can add cleanup here
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")


def get_graph_manager() -> GraphManager:
    """Get or create a graph manager instance."""
    return GraphManager()


def get_graph() -> Any:
    """Convenience function to get the graph instance."""
    return get_graph_manager().graph
