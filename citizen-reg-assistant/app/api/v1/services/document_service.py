import fitz
from app.api.v1.services.llm_service import chat, chat_json, detect_language
from app.api.v1.schemas.document import DocumentRiskResponse, RiskItem
from app.core.prompts import get_document_risk_prompt


def extract_text_from_pdf(file_bytes: bytes) -> str:
    doc  = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text.strip()


async def detect_contract_type(text: str) -> str:
    """Ask Gemini to identify the contract type."""
    messages = [
        {
            "role": "user",
            "content": (
                "Read this contract and identify its type in 3 words or less.\n"
                "Examples: 'house sale', 'car sale', 'employment', "
                "'lease agreement', 'loan agreement', 'business partnership', "
                "'service agreement'.\n"
                "Return only the contract type, nothing else.\n\n"
                f"{text[:2000]}"
            )
        }
    ]
    contract_type = await chat(messages=messages, temperature=0.0)
    return contract_type.strip().lower()


async def analyze_document_risks(
    file_bytes: bytes,
    filename: str,
) -> DocumentRiskResponse:

    # 1. Extract text
    text = extract_text_from_pdf(file_bytes)
    if not text:
        raise ValueError("Could not extract text from the uploaded document.")

    # 2. Auto-detect language of the contract
    detected_language = await detect_language(text)
    print(f"[DOC] Detected language: {detected_language}")

    # 3. Auto-detect contract type
    contract_type = await detect_contract_type(text)
    print(f"[DOC] Detected contract type: {contract_type}")

    # 4. Truncate if too long
    max_chars = 15000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Document truncated]"

    # 5. Get type-specific + language-aware prompt
    system_prompt = get_document_risk_prompt(contract_type, detected_language)

    # 6. Call Gemini in JSON mode
    messages = [
        {
            "role": "user",
            "content": (
                f"Analyze this {contract_type} contract for risks.\n"
                f"The contract is written in {detected_language}.\n"
                f"Your response must be entirely in {detected_language}.\n\n"
                f"{text}"
            )
        }
    ]

    result = await chat_json(
        messages=messages,
        system_prompt=system_prompt,
        temperature=0.1
    )

    # 7. Parse response
    risks = [
        RiskItem(
            clause=r.get("clause", ""),
            risk_level=r.get("risk_level", "MEDIUM").upper(),
            explanation=r.get("explanation", ""),
            recommendation=r.get("recommendation", "")
        )
        for r in result.get("risks", [])
    ]

    high   = sum(1 for r in risks if r.risk_level == "HIGH")
    medium = sum(1 for r in risks if r.risk_level == "MEDIUM")
    low    = sum(1 for r in risks if r.risk_level == "LOW")

    return DocumentRiskResponse(
        contract_type=result.get("contract_type", contract_type),
        detected_language=detected_language,
        summary=result.get("summary", ""),
        missing_clauses=result.get("missing_clauses", []),
        risks=risks,
        total_risks=len(risks),
        high_count=high,
        medium_count=medium,
        low_count=low,
        disclaimer=result.get(
            "disclaimer",
            DocumentRiskResponse.model_fields["disclaimer"].default
        )
    )