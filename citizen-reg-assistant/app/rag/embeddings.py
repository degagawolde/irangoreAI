from google import genai
from app.core.config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


async def get_embedding(text: str) -> list[float]:
    client = get_client()
    result = client.models.embed_content(
        model=settings.GEMINI_EMBED_MODEL,   # reads from .env
        contents=text,
    )
    return result.embeddings[0].values


async def get_embedding_for_document(text: str) -> list[float]:
    client = get_client()
    result = client.models.embed_content(
        model=settings.GEMINI_EMBED_MODEL,   # reads from .env
        contents=text,
    )
    return result.embeddings[0].values