from datetime import datetime, timezone
from elasticsearch import AsyncElasticsearch
from app.core.config import settings

_client = None


def get_es_client() -> AsyncElasticsearch:
    global _client
    if _client is None:
        _client = AsyncElasticsearch(
            hosts=[settings.ES_URL],
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3
        )
    return _client


async def close_es_client():
    global _client
    if _client:
        await _client.close()
        _client = None


async def create_index():
    client = get_es_client()

    if await client.indices.exists(index=settings.ES_INDEX):
        print(f"[ES] Index '{settings.ES_INDEX}' already exists")
        return

    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "legal_analyzer": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "stop"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "text": {
                    "type": "text",
                    "analyzer": "legal_analyzer",
                    "fields": {
                        "keyword": {"type": "keyword"}
                    }
                },
                "embedding": {
                    "type": "dense_vector",
                    "dims": settings.ES_VECTOR_DIMS,
                    "index": True,
                    "similarity": "cosine"
                },
                "source":       {"type": "keyword"},
                "article":      {"type": "keyword"},
                "jurisdiction": {"type": "keyword"},
                "page":         {"type": "integer"},
                "ingested_at":  {"type": "date"}
            }
        }
    }

    await client.indices.create(index=settings.ES_INDEX, body=mapping)
    print(f"[ES] Index '{settings.ES_INDEX}' created")


async def index_document(
    doc_id: str,
    text: str,
    embedding: list[float],
    source: str,
    jurisdiction: str,
    article: str = "",
    page: int = 0,
):
    client = get_es_client()
    await client.index(
        index=settings.ES_INDEX,
        id=doc_id,
        document={
            "text":         text,
            "embedding":    embedding,
            "source":       source,
            "article":      article,
            "jurisdiction": jurisdiction,
            "page":         page,
            "ingested_at":  datetime.now(timezone.utc).isoformat()
        }
    )


async def _keyword_search(
    query_text: str,
    jurisdiction: str,
    n_results: int
) -> list[dict]:
    """BM25 keyword search."""
    client = get_es_client()

    jurisdiction_filter = (
        {"term": {"jurisdiction": jurisdiction}}
        if jurisdiction else {"match_all": {}}
    )

    response = await client.search(
        index=settings.ES_INDEX,
        body={
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["text^2", "source", "article"],
                            "type": "best_fields"
                        }
                    },
                    "filter": jurisdiction_filter
                }
            },
            "size": n_results,
            "_source": ["text", "source", "article", "jurisdiction", "page"]
        }
    )

    return [
        {
            "id":    hit["_id"],
            "text":  hit["_source"].get("text", ""),
            "source":       hit["_source"].get("source", ""),
            "article":      hit["_source"].get("article", ""),
            "jurisdiction": hit["_source"].get("jurisdiction", jurisdiction),
            "page":         hit["_source"].get("page", 0),
            "score":        hit["_score"]
        }
        for hit in response["hits"]["hits"]
    ]


async def _vector_search(
    query_embedding: list[float],
    jurisdiction: str,
    n_results: int
) -> list[dict]:
    """Semantic vector search using kNN."""
    client = get_es_client()

    jurisdiction_filter = (
        {"term": {"jurisdiction": jurisdiction}}
        if jurisdiction else None
    )

    knn = {
        "field": "embedding",
        "query_vector": query_embedding,
        "k": n_results,
        "num_candidates": 50,
    }
    if jurisdiction_filter:
        knn["filter"] = jurisdiction_filter

    response = await client.search(
        index=settings.ES_INDEX,
        body={
            "knn": knn,
            "size": n_results,
            "_source": ["text", "source", "article", "jurisdiction", "page"]
        }
    )

    return [
        {
            "id":    hit["_id"],
            "text":  hit["_source"].get("text", ""),
            "source":       hit["_source"].get("source", ""),
            "article":      hit["_source"].get("article", ""),
            "jurisdiction": hit["_source"].get("jurisdiction", jurisdiction),
            "page":         hit["_source"].get("page", 0),
            "score":        hit["_score"]
        }
        for hit in response["hits"]["hits"]
    ]


def _reciprocal_rank_fusion(
    keyword_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
    keyword_weight: float = 0.3,
    vector_weight: float = 0.7,
) -> list[dict]:
    """
    Merge keyword and vector results using Reciprocal Rank Fusion.
    RRF score = keyword_weight * 1/(k + rank) + vector_weight * 1/(k + rank)
    """
    scores = {}
    docs   = {}

    # Score keyword results
    for rank, doc in enumerate(keyword_results, 1):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + keyword_weight * (1 / (k + rank))
        docs[doc_id]   = doc

    # Score vector results
    for rank, doc in enumerate(vector_results, 1):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + vector_weight * (1 / (k + rank))
        docs[doc_id]   = doc

    # Sort by combined RRF score
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)

    return [
        {**docs[doc_id], "score": scores[doc_id]}
        for doc_id in sorted_ids
    ]


async def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    jurisdiction: str = "Ethiopia",
    n_results: int = 5,
) -> list[dict]:
    """
    Hybrid search: BM25 + vector, merged with Reciprocal Rank Fusion.
    Compatible with Elasticsearch 8.12.
    """
    # Run both searches in parallel
    import asyncio
    keyword_results, vector_results = await asyncio.gather(
        _keyword_search(query_text, jurisdiction, n_results),
        _vector_search(query_embedding, jurisdiction, n_results)
    )

    # Merge with RRF
    merged = _reciprocal_rank_fusion(
        keyword_results,
        vector_results,
        keyword_weight=0.3,
        vector_weight=0.7
    )

    return merged[:n_results]


async def delete_index():
    client = get_es_client()
    if await client.indices.exists(index=settings.ES_INDEX):
        await client.indices.delete(index=settings.ES_INDEX)
        print(f"[ES] Index '{settings.ES_INDEX}' deleted")