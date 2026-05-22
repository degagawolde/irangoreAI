from fastapi import APIRouter, UploadFile, File, HTTPException
from app.api.v1.schemas.document import ContractAnalysisResponse
from app.api.v1.services.document_service import analyze_contract
from app.api.v1.helpers.pdf_parser import SUPPORTED_EXTENSIONS

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/analyze",
    response_model=ContractAnalysisResponse,
    summary="Analyze a contract",
    description=(
        "Upload a contract as PDF, scanned PDF, screenshot, or photo. "
        "Supported formats: PDF, JPG, PNG, WEBP, GIF, BMP. "
        "The system auto-detects language (English, Amharic, Oromiffa) "
        "and contract type, then returns full structured analysis."
    )
)
async def analyze_document(file: UploadFile = File(...)):

    # Validate file extension
    filename  = file.filename or "document"
    ext       = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        )

    # Read file
    file_bytes = await file.read()

    # Validate size (50MB max)
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 50MB."
        )

    # Validate not empty
    if len(file_bytes) < 100:
        raise HTTPException(
            status_code=400,
            detail="File appears to be empty or corrupted."
        )

    try:
        return await analyze_contract(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Contract analysis failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )