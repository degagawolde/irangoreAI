from app.rag.embeddings import get_embedding, get_embedding_for_document
from app.rag.elastic_store import hybrid_search, index_document


async def retrieve_relevant_laws(
    query: str,
    jurisdiction: str = "Ethiopia",
    n_results: int = 5
) -> list[dict]:
    """
    Hybrid search — BM25 + semantic vector via Elasticsearch RRF.
    Works natively with Amharic, Oromiffa, Tigrinya, and English.
    """
    query_embedding = await get_embedding(query)
    return await hybrid_search(
        query_text=query,
        query_embedding=query_embedding,
        jurisdiction=jurisdiction,
        n_results=n_results
    )


async def ingest_legal_document(
    text: str,
    source: str,
    jurisdiction: str,
    article: str = "",
    doc_id: str = None,
    page: int = 0
):
    """Embed and index a legal document chunk into Elasticsearch."""
    embedding = await get_embedding_for_document(text)
    await index_document(
        doc_id=doc_id or f"{source}_{article}_{hash(text)}",
        text=text,
        embedding=embedding,
        source=source,
        jurisdiction=jurisdiction,
        article=article,
        page=page
    )