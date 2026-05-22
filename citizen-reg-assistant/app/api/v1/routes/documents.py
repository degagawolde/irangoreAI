from fastapi import APIRouter, UploadFile, File, HTTPException
from app.api.v1.schemas.document import ContractAnalysisResponse
from app.api.v1.services.document_service import analyze_contract

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_TYPES = {
    "application/pdf",
    "application/octet-stream"
}


@router.post(
    "/analyze",
    response_model=ContractAnalysisResponse,
    summary="Analyze a contract",
    description=(
        "Upload a contract PDF in English, Amharic, or Afaan Oromo. "
        "The system auto-detects the language and contract type, then returns "
        "a full structured analysis including obligations, restrictions, "
        "consequences, risks, and missing clauses — all in the contract's language."
    )
)
async def analyze_document(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file."
        )

    # Validate file size (max 20MB)
    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 50MB."
            
        )

    if len(file_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="File appears to be empty or corrupted."
        )

    try:
        return await analyze_contract(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Contract analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )