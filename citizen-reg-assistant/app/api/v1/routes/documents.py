from fastapi import APIRouter, UploadFile, File, HTTPException
from app.api.v1.schemas.document import DocumentRiskResponse
from app.api.v1.services.document_service import analyze_document_risks

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/analyze", response_model=DocumentRiskResponse)
async def analyze_document(file: UploadFile = File(...)):
    """
    Upload a contract PDF in any language.
    Auto-detects language and contract type.
    Returns risks and missing clauses in the same language.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()

    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")

    try:
        return await analyze_document_risks(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))