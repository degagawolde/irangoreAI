from app.rag.embeddings import get_embedding, get_embedding_for_document
from app.rag.vector_store import get_collection


async def retrieve_relevant_laws(
    query: str,
    jurisdiction: str = "Ethiopia",
    n_results: int = 5
) -> list[dict]:
    """
    Retrieve most relevant legal documents for a query.
    Gemini text-embedding-004 handles Amharic, Oromiffa,
    Tigrinya natively — no translation needed.
    """
    collection = get_collection()

    # Gemini embeddings are multilingual — embed query as-is
    query_embedding = await get_embedding(query)

    where_filter = {"jurisdiction": jurisdiction} if jurisdiction else None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    retrieved = []
    if results and results["documents"]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            retrieved.append({
                "text":         doc,
                "source":       meta.get("source", "Unknown"),
                "jurisdiction": meta.get("jurisdiction", jurisdiction),
                "article":      meta.get("article", ""),
                "distance":     dist
            })

    return retrieved


async def ingest_legal_document(
    text: str,
    source: str,
    jurisdiction: str,
    article: str = "",
    doc_id: str = None
):
    """Add a legal document chunk to the vector store."""
    collection = get_collection()
    embedding = await get_embedding_for_document(text)

    collection.add(
        ids=[doc_id or f"{source}_{article}_{hash(text)}"],
        embeddings=[embedding],
        documents=[text],
        metadatas=[{
            "source":       source,
            "jurisdiction": jurisdiction,
            "article":      article
        }]
    )