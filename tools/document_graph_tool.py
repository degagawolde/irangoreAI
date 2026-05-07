"""Document loading, chunking, and graph ingestion tools for GraphRAG."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_settings
from core.exceptions import GraphException
from core.logger import get_logger
from graph import get_graph
from llms import get_embeddings

from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = get_logger(__name__)


SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".rst"}


class DocumentGraphIngestionTool:
    """Tool to load documents, chunk them, and ingest into Neo4j graph."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.graph = get_graph()
        self.embeddings = get_embeddings()

    def load_documents(self, path: str) -> List[Dict[str, Any]]:
        """Load text-like documents from a file or directory."""
        root = Path(path)
        if not root.exists():
            raise GraphException(f"Path does not exist: {path}")

        files: List[Path] = []
        if root.is_file():
            files = [root]
        else:
            files = [
                p
                for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]

        documents: List[Dict[str, Any]] = []
        for file_path in files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
                if not text:
                    continue
                documents.append(
                    {
                        "source_path": str(file_path.resolve()),
                        "title": file_path.name,
                        "content": text,
                    }
                )
            except Exception as e:
                logger.warning(f"Skipping unreadable file {file_path}: {str(e)}")

        if not documents:
            raise GraphException(
                f"No supported documents found in {path}. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
            )

        logger.info(f"Loaded {len(documents)} documents from {path}")
        return documents

    def chunk_documents(
        self,
        documents: List[Dict[str, Any]],
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> List[Dict[str, Any]]:
        """Chunk loaded documents for graph/vector storage."""
        if chunk_overlap >= chunk_size:
            raise GraphException("chunk_overlap must be smaller than chunk_size")

        try:
           
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
        except Exception as e:
            raise GraphException(f"Failed to initialize text splitter: {str(e)}")

        chunk_rows: List[Dict[str, Any]] = []
        for doc in documents:
            document_id = hashlib.sha256(doc["source_path"].encode("utf-8")).hexdigest()
            chunks = splitter.split_text(doc["content"])
            for idx, chunk_text in enumerate(chunks):
                normalized = chunk_text.strip()
                if not normalized:
                    continue
                chunk_rows.append(
                    {
                        "document_id": document_id,
                        "document_title": doc["title"],
                        "source_path": doc["source_path"],
                        "chunk_index": idx,
                        "chunk_id": f"{document_id}:{idx}",
                        "text": normalized,
                    }
                )

        if not chunk_rows:
            raise GraphException("Chunking produced no content")

        logger.info(f"Created {len(chunk_rows)} chunks from {len(documents)} documents")
        return chunk_rows

    def ingest_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Ingest chunks into Neo4j as a document knowledge graph."""
        created_at = datetime.now(timezone.utc).isoformat()

        texts = [c["text"] for c in chunks]
        vectors = self.embeddings.embed_documents(texts)
        if len(vectors) != len(chunks):
            raise GraphException("Embedding count did not match chunk count")

        rows: List[Dict[str, Any]] = []
        for chunk, embedding in zip(chunks, vectors):
            row = {**chunk, "embedding": embedding, "created_at": created_at}
            rows.append(row)

        self._ensure_vector_index(dimensions=len(vectors[0]))

        upsert_query = """
UNWIND $rows AS row
MERGE (d:Document {id: row.document_id})
  ON CREATE SET
    d.title = row.document_title,
    d.source_path = row.source_path,
    d.created_at = row.created_at
  ON MATCH SET
    d.title = row.document_title,
    d.source_path = row.source_path
MERGE (c:Chunk {id: row.chunk_id})
  ON CREATE SET
    c.created_at = row.created_at
SET
  c.document_id = row.document_id,
  c.chunk_index = row.chunk_index,
  c.text = row.text,
  c.embedding = row.embedding,
  c.source_path = row.source_path
MERGE (d)-[:HAS_CHUNK]->(c)
WITH row, c
OPTIONAL MATCH (prev:Chunk {id: row.document_id + ':' + toString(row.chunk_index - 1)})
FOREACH (_ IN CASE WHEN prev IS NULL THEN [] ELSE [1] END |
  MERGE (prev)-[:NEXT_CHUNK]->(c)
)
"""
        self.graph.query(upsert_query, params={"rows": rows})

        doc_count = len({c["document_id"] for c in chunks})
        chunk_count = len(chunks)
        logger.info(f"Ingested {doc_count} documents and {chunk_count} chunks")
        return {"documents": doc_count, "chunks": chunk_count}

    def ingest_documents(
        self,
        path: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> Dict[str, int]:
        """Full ingestion flow: load -> chunk -> embed -> ingest."""
        documents = self.load_documents(path)
        chunks = self.chunk_documents(
            documents=documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return self.ingest_chunks(chunks)

    def _ensure_vector_index(self, dimensions: int) -> None:
        """Ensure vector index exists for chunk embeddings."""
        query = f"""
CREATE VECTOR INDEX {self.settings.VECTOR_INDEX_NAME} IF NOT EXISTS
FOR (c:{self.settings.VECTOR_NODE_LABEL}) ON (c.{self.settings.VECTOR_EMBEDDING_PROPERTY})
OPTIONS {{
  indexConfig: {{
    `vector.dimensions`: $dimensions,
    `vector.similarity_function`: 'cosine'
  }}
}}
"""
        try:
            self.graph.query(query, params={"dimensions": dimensions})
        except Exception as e:
            raise GraphException(f"Failed to create/verify vector index: {str(e)}")


def get_document_graph_ingestion_tool() -> DocumentGraphIngestionTool:
    """Get a document graph ingestion tool instance."""
    return DocumentGraphIngestionTool()


def ingest_documents_to_graph(
    path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> Dict[str, int]:
    """Convenience function to ingest documents from filesystem into graph."""
    tool = get_document_graph_ingestion_tool()
    return tool.ingest_documents(path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)


def ingest_documents_tool(payload: str) -> str:
    """Agent-friendly wrapper for document ingestion tool.

    Expected payload JSON:
    {"path": "./docs", "chunk_size": 1000, "chunk_overlap": 150}
    """
    try:
        data = json.loads(payload)
        path = data["path"]
        chunk_size = int(data.get("chunk_size", 1000))
        chunk_overlap = int(data.get("chunk_overlap", 150))

        result = ingest_documents_to_graph(
            path=path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return (
            f"Ingestion complete. Documents: {result['documents']}, "
            f"Chunks: {result['chunks']}"
        )
    except KeyError:
        return "Invalid payload. Provide JSON with at least: {'path': '...'}"
    except Exception as e:
        return f"Document ingestion failed: {str(e)}"
