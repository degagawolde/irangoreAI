"""Document discovery and listing tools for graph-based document retrieval."""

from typing import List, Dict, Any
from core.logger import get_logger
from core.exceptions import GraphException
from config import get_settings
from graph import get_graph
from llms import get_embeddings

logger = get_logger(__name__)


class DocumentDiscoveryTool:
    """Tool for discovering and listing relevant documents."""

    _instance = None
    _graph = None
    _embeddings = None
    _settings = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize document discovery tool."""
        if self._graph is None:
            self._initialize()

    def _initialize(self) -> None:
        """Initialize graph and embeddings."""
        try:
            self._settings = get_settings()
            self._graph = get_graph()
            self._embeddings = get_embeddings()
            logger.info("Document discovery tool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize document discovery tool: {str(e)}")
            raise GraphException(f"Failed to initialize document discovery tool: {str(e)}")

    def list_all_documents(self) -> List[Dict[str, Any]]:
        """List all available documents in the knowledge graph.
        
        Returns:
            List of documents with metadata (title, id, chunk count, source)
        """
        try:
            query = """
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, count(c) as chunk_count
            RETURN
                d.id as document_id,
                d.title as title,
                d.source_path as source_path,
                chunk_count,
                properties(d) as metadata
            ORDER BY d.title
            """
            
            logger.debug("Querying all documents")
            results = self._graph.query(query)
            
            documents = []
            for record in results:
                documents.append({
                    "document_id": record["document_id"],
                    "title": record["title"],
                    "source_path": record["source_path"],
                    "chunk_count": record["chunk_count"],
                    "metadata": record["metadata"]
                })
            
            logger.info(f"Found {len(documents)} documents in knowledge graph")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}")
            raise GraphException(f"Failed to list documents: {str(e)}")

    def find_documents_by_name(self, name_pattern: str) -> List[Dict[str, Any]]:
        """Find documents by name pattern matching.
        
        Searches for documents where title contains the pattern (case-insensitive).
        Useful for queries that explicitly mention document types like:
        - "statement of purpose"
        - "CV" or "resume"
        - "cover letter"
        
        Args:
            name_pattern: Part or full name of document to search for
            
        Returns:
            List of matching documents
        """
        try:
            pattern = f"%{name_pattern}%"
            query = """
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WHERE toLower(d.title) CONTAINS toLower($pattern)
            WITH d, count(c) as chunk_count
            RETURN
                d.id as document_id,
                d.title as title,
                d.source_path as source_path,
                chunk_count,
                properties(d) as metadata
            ORDER BY d.title
            """
            
            logger.debug(f"Searching for documents matching pattern: {name_pattern}")
            results = self._graph.query(query, {"pattern": name_pattern})
            
            documents = []
            for record in results:
                documents.append({
                    "document_id": record["document_id"],
                    "title": record["title"],
                    "source_path": record["source_path"],
                    "chunk_count": record["chunk_count"],
                    "metadata": record["metadata"],
                    "match_type": "name_match"
                })
            
            logger.info(f"Found {len(documents)} documents matching pattern: {name_pattern}")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to find documents by name: {str(e)}")
            raise GraphException(f"Failed to find documents by name: {str(e)}")

    def find_documents_smart(self, query: str, name_patterns: List[str] = None) -> List[Dict[str, Any]]:
        """Smart document finding that combines name matching and semantic search.
        
        This method:
        1. First tries to find documents by name if patterns are provided
        2. Falls back to semantic similarity search
        3. Combines results intelligently
        
        Args:
            query: The search query
            name_patterns: Optional list of document name patterns to search for first
                          e.g., ["statement of purpose", "CV"]
            
        Returns:
            List of documents (name matches first, then semantic matches)
        """
        try:
            documents = []
            
            # Step 1: Try name-based matching if patterns provided
            if name_patterns:
                logger.debug(f"Attempting name-based matching for patterns: {name_patterns}")
                for pattern in name_patterns:
                    if pattern.strip():
                        matching_docs = self.find_documents_by_name(pattern.strip())
                        documents.extend(matching_docs)
                
                # Remove duplicates
                seen = set()
                unique_docs = []
                for doc in documents:
                    doc_id = doc["document_id"]
                    if doc_id not in seen:
                        seen.add(doc_id)
                        unique_docs.append(doc)
                
                if unique_docs:
                    logger.info(f"Found {len(unique_docs)} documents via name matching")
                    return unique_docs
            
            # Step 2: Fall back to semantic search
            logger.debug("Falling back to semantic search")
            documents = self.find_relevant_documents(query, threshold=0.3)
            return documents
            
        except Exception as e:
            logger.error(f"Failed in smart document search: {str(e)}")
            raise GraphException(f"Failed in smart document search: {str(e)}")

    def find_relevant_documents(self, query: str, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Find documents relevant to a query using semantic similarity.
        
        This method:
        1. Embeds the query
        2. Finds the most similar chunks
        3. Identifies which documents those chunks belong to
        4. Returns documents ranked by relevance
        
        Args:
            query: The search query
            threshold: Minimum relevance score (0-1)
            
        Returns:
            List of relevant documents with relevance scores
        """
        try:
            # Get query embedding
            query_vector = self._embeddings.embed_query(query)
            logger.debug(f"Finding relevant documents for query: {query}")
            
            # Find relevant chunks and their parent documents
            cypher_query = """
            CALL db.index.vector.queryNodes($vector_index_name, 20, $query_vector)
            YIELD node as chunk, score
            WHERE score > $threshold
            MATCH (doc:Document)-[:HAS_CHUNK]->(chunk)
            WITH doc, score, chunk
            WITH doc, max(score) as max_score, collect(DISTINCT chunk.id) as relevant_chunks
            RETURN
                doc.id as document_id,
                doc.title as title,
                doc.source_path as source_path,
                max_score as relevance_score,
                size(relevant_chunks) as relevant_chunk_count,
                properties(doc) as metadata
            ORDER BY max_score DESC
            """
            
            params = {
                "vector_index_name": self._settings.VECTOR_INDEX_NAME,
                "query_vector": query_vector,
                "threshold": threshold
            }
            
            results = self._graph.query(cypher_query, params)
            
            documents = []
            for record in results:
                documents.append({
                    "document_id": record["document_id"],
                    "title": record["title"],
                    "source_path": record["source_path"],
                    "relevance_score": float(record["relevance_score"]),
                    "relevant_chunk_count": record["relevant_chunk_count"],
                    "metadata": record["metadata"]
                })
            
            logger.info(f"Found {len(documents)} relevant documents")
            return documents
            
        except Exception as e:
            logger.error(f"Failed to find relevant documents: {str(e)}")
            raise GraphException(f"Failed to find relevant documents: {str(e)}")

    def get_document_details(self, document_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific document.
        
        Args:
            document_id: The ID of the document
            
        Returns:
            Document details including metadata and chunk summary
        """
        try:
            query = """
            MATCH (d:Document {id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
            WITH d, count(c) as total_chunks, collect(DISTINCT c.id) as chunk_ids
            RETURN
                d.id as document_id,
                d.title as title,
                d.source_path as source_path,
                total_chunks,
                chunk_ids,
                properties(d) as metadata
            """
            
            params = {"doc_id": document_id}
            logger.debug(f"Getting details for document: {document_id}")
            
            result = self._graph.query(query, params)
            
            if not result:
                raise GraphException(f"Document not found: {document_id}")
            
            record = result[0]
            return {
                "document_id": record["document_id"],
                "title": record["title"],
                "source_path": record["source_path"],
                "total_chunks": record["total_chunks"],
                "chunk_ids": record["chunk_ids"],
                "metadata": record["metadata"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get document details: {str(e)}")
            raise GraphException(f"Failed to get document details: {str(e)}")

    def get_chunks_from_documents(
        self, document_ids: List[str], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get chunks from specific documents.
        
        Args:
            document_ids: List of document IDs to retrieve chunks from
            limit: Maximum number of chunks to return per document
            
        Returns:
            List of chunks with metadata
        """
        try:
            if not document_ids:
                return []
            
            # Build placeholders for the document IDs
            ids_placeholder = ",".join([f"${i}" for i in range(len(document_ids))])
            
            query = f"""
            MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)
            WHERE d.id IN [{ids_placeholder}]
            RETURN
                d.id as document_id,
                d.title as document_title,
                c.id as chunk_id,
                c.text as text,
                c.chunk_index as chunk_index,
                elementId(c) as element_id,
                properties(c) as metadata
            ORDER BY d.id, c.chunk_index
            LIMIT $limit
            """
            
            params = {str(i): doc_id for i, doc_id in enumerate(document_ids)}
            params["limit"] = limit
            
            logger.debug(f"Retrieving chunks from {len(document_ids)} documents")
            results = self._graph.query(query, params)
            
            chunks = []
            for record in results:
                chunks.append({
                    "document_id": record["document_id"],
                    "document_title": record["document_title"],
                    "chunk_id": record["chunk_id"],
                    "text": record["text"],
                    "chunk_index": record["chunk_index"],
                    "element_id": record["element_id"],
                    "metadata": record["metadata"]
                })
            
            logger.info(f"Retrieved {len(chunks)} chunks from {len(document_ids)} documents")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to get chunks from documents: {str(e)}")
            raise GraphException(f"Failed to get chunks from documents: {str(e)}")


def get_document_discovery_tool() -> DocumentDiscoveryTool:
    """Get document discovery tool instance."""
    return DocumentDiscoveryTool()


def list_documents() -> str:
    """List all available documents as a formatted string for agent use."""
    tool = get_document_discovery_tool()
    documents = tool.list_all_documents()
    
    if not documents:
        return "No documents found in the knowledge graph."
    
    result = "Available documents:\n"
    for i, doc in enumerate(documents, 1):
        result += f"{i}. {doc['title']} ({doc['chunk_count']} chunks, {doc['source_path']})\n"
    
    return result


def find_relevant_documents(query: str) -> str:
    """Find documents relevant to a query and return as formatted string."""
    tool = get_document_discovery_tool()
    documents = tool.find_relevant_documents(query, threshold=0.3)
    
    if not documents:
        return f"No relevant documents found for query: {query}"
    
    result = f"Relevant documents for '{query}':\n"
    for i, doc in enumerate(documents, 1):
        score = doc['relevance_score']
        result += f"{i}. {doc['title']} (relevance: {score:.2%}, {doc['relevant_chunk_count']} matching chunks)\n"
    
    return result


def search_documents_by_name(name_pattern: str) -> str:
    """Search for documents by name pattern.
    
    This is useful when a query explicitly mentions document types like:
    - 'statement of purpose'
    - 'resume or CV'
    - 'cover letter'
    
    Args:
        name_pattern: The document name or type to search for
        
    Returns:
        Formatted list of matching documents
    """
    tool = get_document_discovery_tool()
    documents = tool.find_documents_by_name(name_pattern)
    
    if not documents:
        return f"No documents found matching '{name_pattern}'"
    
    result = f"Documents matching '{name_pattern}':\n"
    for i, doc in enumerate(documents, 1):
        result += f"{i}. {doc['title']} ({doc['chunk_count']} chunks, {doc['source_path']})\n"
    
    return result





def get_chunks_from_query_documents(query: str, limit: int = 20) -> str:
    """Find relevant documents for a query and retrieve their chunks.
    
    This is the primary workflow: identify relevant docs -> get chunks.
    
    Args:
        query: The search query
        limit: Maximum chunks to retrieve
        
    Returns:
        Formatted chunks as a string for agent use
    """
    try:
        tool = get_document_discovery_tool()
        
        # Step 1: Find relevant documents
        relevant_docs = tool.find_relevant_documents(query, threshold=0.3)
        
        if not relevant_docs:
            return f"No relevant documents found for query: {query}"
        
        # Step 2: Extract document IDs
        doc_ids = [doc['document_id'] for doc in relevant_docs]
        
        # Step 3: Get chunks from those documents
        chunks = tool.get_chunks_from_documents(doc_ids, limit=limit)
        
        if not chunks:
            return "Found relevant documents but no chunks to retrieve."
        
        # Format chunks for agent
        result = f"Retrieved {len(chunks)} chunks from {len(doc_ids)} relevant documents:\n\n"
        
        current_doc = None
        for chunk in chunks:
            if chunk['document_id'] != current_doc:
                current_doc = chunk['document_id']
                result += f"\n=== {chunk['document_title']} ===\n"
            
            result += f"\n[Chunk {chunk['chunk_index']}]:\n{chunk['text'][:500]}...\n"
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get chunks from query documents: {str(e)}")
        return f"Error retrieving documents: {str(e)}"
