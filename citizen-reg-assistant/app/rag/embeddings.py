import httpx
from google import genai
from app.core.config import settings

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _gemini_client


async def _embed_gemini(text: str) -> list[float]:
    client = _get_gemini_client()
    result = client.models.embed_content(
        model=settings.GEMINI_EMBED_MODEL,
        contents=text,
    )
    return result.embeddings[0].values


async def _embed_ollama(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": settings.OLLAMA_EMBED_MODEL,
                "prompt": text
            }
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def get_embedding(text: str) -> list[float]:
    """Query embedding — used when searching."""
    if settings.EMBED_PROVIDER == "gemini":
        return await _embed_gemini(text)
    return await _embed_ollama(text)


async def get_embedding_for_document(text: str) -> list[float]:
    """Document embedding — used when ingesting."""
    if settings.EMBED_PROVIDER == "gemini":
        return await _embed_gemini(text)
    return await _embed_ollama(text)