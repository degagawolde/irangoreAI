from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.routes import regulations, documents, ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — create ES index
    from app.rag.elastic_store import create_index
    await create_index()
    print("[ES] Ready")

    yield

    # Shutdown — close ES connection
    from app.rag.elastic_store import close_es_client
    await close_es_client()
    print("[ES] Connection closed")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered legal information assistant for Ethiopian law",
    lifespan=lifespan
)

app.include_router(regulations.router, prefix="/api/v1")
app.include_router(documents.router,   prefix="/api/v1")
app.include_router(ingest.router,      prefix="/api/v1")


@app.get("/health")
async def health():
    return {
        "status":         "ok",
        "llm_provider":   settings.LLM_PROVIDER,
        "embed_provider": settings.EMBED_PROVIDER,
        "llm_model": (
            settings.GEMINI_LLM_MODEL
            if settings.LLM_PROVIDER == "gemini"
            else settings.OLLAMA_LLM_MODEL
        ),
        "embed_model": (
            settings.GEMINI_EMBED_MODEL
            if settings.EMBED_PROVIDER == "gemini"
            else settings.OLLAMA_EMBED_MODEL
        ),
    }