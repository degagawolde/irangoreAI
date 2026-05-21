from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from app.api.v1.helpers.pdf_parser import parse_pdf_into_chunks
from app.rag.retriever import ingest_legal_document

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


class IngestResponse(BaseModel):
    filename: str
    source: str
    jurisdiction: str
    chunks_ingested: int
    message: str


@router.post("/pdf", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    source: str = Form(...),        # e.g. "Proclamation No. 1180/2020"
    jurisdiction: str = Form(default="Ethiopia"),
):
    """
    Upload a PDF proclamation or legal document.
    It will be chunked and embedded into the vector store automatically.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()

    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 20MB.")

    # Parse into chunks
    chunks = parse_pdf_into_chunks(file_bytes, chunk_size=600, overlap=100)

    if not chunks:
        raise HTTPException(status_code=422, detail="Could not extract text from PDF.")

    # Embed and store each chunk
    ingested = 0
    errors = 0

    for chunk in chunks:
        try:
            doc_id = f"{source}_p{chunk.page}_c{chunk.chunk_index}"
            await ingest_legal_document(
                text=chunk.text,
                source=source,
                jurisdiction=jurisdiction,
                article=f"Page {chunk.page}",
                doc_id=doc_id
            )
            ingested += 1
        except Exception:
            errors += 1

    if ingested == 0:
        raise HTTPException(status_code=500, detail="All chunks failed to ingest.")

    return IngestResponse(
        filename=file.filename,
        source=source,
        jurisdiction=jurisdiction,
        chunks_ingested=ingested,
        message=f"Successfully ingested {ingested} chunks. {errors} failed."
    )