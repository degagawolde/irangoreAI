from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from app.api.v1.schemas.document import ContractAnalysisResponse
from app.api.v1.services.document_service import analyze_contract
from app.api.v1.helpers.pdf_parser import SUPPORTED_EXTENSIONS
from app.api.dependencies import DBSession
from app.models.query_log import QueryLog
import json

router = APIRouter(prefix="/documents", tags=["Documents"])


async def _save_analysis_log(
    db,
    filename: str,
    contract_type: str,
    language: str,
    total_risks: int,
    overall_risk: str,
    issue_categories: list
):
    """
    Runs AFTER response is sent to user.
    User never waits for this.
    """
    try:
        log = QueryLog(
            question=f"Contract analysis: {filename}",
            jurisdiction="Ethiopia",
            answer=f"Type: {contract_type} | Language: {language} | "
                   f"Risks: {total_risks} | Overall: {overall_risk}",
            sources=json.dumps([
                {"category": c.category, "count": c.count,
                 "risk_level": c.risk_level}
                for c in issue_categories
            ])
        )
        db.add(log)
        await db.commit()
        print(f"[BG] Analysis logged to database")
    except Exception as e:
        print(f"[BG] Failed to log analysis: {e}")


@router.post(
    "/analyze",
    response_model=ContractAnalysisResponse,
    summary="Analyze a contract",
    description=(
        "Upload a contract as PDF, scanned PDF, screenshot, or photo. "
        "Supported: PDF, JPG, PNG, WEBP, GIF, BMP. "
        "Auto-detects language (English, Amharic, Oromiffa) and contract type."
    )
)
async def analyze_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,   # ← injected by FastAPI
    db: DBSession,
):
    # Validate file extension
    filename = file.filename or "document"
    ext      = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        )

    # Read and validate file
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
        # This is the slow part — user waits for this
        result = await analyze_contract(file_bytes, filename)

        # This runs AFTER response is sent — user does NOT wait
        background_tasks.add_task(
            _save_analysis_log,
            db=db,
            filename=filename,
            contract_type=result.contract_type,
            language=result.detected_language,
            total_risks=result.total_risks,
            overall_risk=result.overall_risk_level,
            issue_categories=result.issue_categories
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Contract analysis failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )