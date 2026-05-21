from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.routes import regulations, documents, ingest

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="AI-powered legal information assistant for Ethiopian law"
)

app.include_router(regulations.router, prefix="/api/v1")
app.include_router(documents.router,   prefix="/api/v1")
app.include_router(ingest.router,      prefix="/api/v1")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model":  settings.GEMINI_LLM_MODEL,
        "embed":  settings.GEMINI_EMBED_MODEL
    }