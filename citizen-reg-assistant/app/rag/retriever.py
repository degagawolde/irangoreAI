from app.rag.embeddings import get_embedding, get_embedding_for_document
from app.rag.elastic_store import hybrid_search, index_document


def _is_likely_english(text: str) -> bool:
    """Check if text is mostly ASCII (English)."""
    if not text:
        return True
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
    return ascii_ratio > 0.85


async def _translate_to_english(text: str) -> str:
    """
    Translate non-English query to English for better retrieval.
    Only used for embedding — the LLM still responds in original language.
    """
    from app.api.v1.services.llm_service import chat
    messages = [
        {
            "role": "user",
            "content": (
                "Translate the following text to English. "
                "Return only the translation, nothing else.\n\n"
                f"{text}"
            )
        }
    ]
    translated = await chat(messages=messages, temperature=0.0)
    return translated.strip()


async def retrieve_relevant_laws(
    query: str,
    jurisdiction: str = "Ethiopia",
    n_results: int = 5
) -> list[dict]:
    """
    Hybrid search — BM25 + semantic vector via manual RRF.
    Translates non-English queries to English before embedding
    since nomic-embed-text is English-only.
    LLM still responds in the original language.
    """
    # Translate for retrieval if not English
    retrieval_query = query
    if not _is_likely_english(query):
        retrieval_query = await _translate_to_english(query)
        print(f"[RAG] Translated for retrieval: '{query[:50]}' → '{retrieval_query}'")

    query_embedding = await get_embedding(retrieval_query)

    return await hybrid_search(
        query_text=retrieval_query,   # English for BM25
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