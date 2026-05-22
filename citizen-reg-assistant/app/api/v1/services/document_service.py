import re
import fitz
from app.core.config import settings
from app.api.v1.services.llm_service import chat, chat_json, detect_language
from app.api.v1.schemas.document import (
    ContractAnalysisResponse,
    Party,
    Consequence,
    RiskItem
)
from app.core.prompts import get_contract_analysis_prompt


# ── PDF Extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> tuple[str, int]:
    """
    Extract all text from PDF.
    Returns (full_text, total_pages).
    """
    doc        = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text = []

    for page in doc:
        text = page.get_text().strip()
        if text:
            pages_text.append(text)

    return "\n\n".join(pages_text), len(pages_text)


def smart_truncate(
    text: str,
    total_pages: int,
    max_chars: int = 12000
) -> tuple[str, str]:
    """
    Smart truncation for large legal documents.

    Strategy by document size:
    - Small  (≤ max_chars)       → full text, no truncation
    - Medium (≤ 2x max_chars)    → first 60% + last 40%
    - Large  (> 2x max_chars)    → first 40% + middle 35% + last 25%

    Returns (truncated_text, truncation_note)
    """
    total_chars = len(text)

    # Small — no truncation needed
    if total_chars <= max_chars:
        return text, ""

    # Medium document
    if total_chars <= max_chars * 2:
        first     = int(max_chars * 0.60)
        last      = max_chars - first
        truncated = (
            text[:first]
            + "\n\n[... middle section not analyzed ...]\n\n"
            + text[-last:]
        )
        note = (
            f"Document has {total_chars:,} chars (~{total_pages} pages). "
            f"Analyzed first and last sections."
        )
        return truncated, note

    # Large document — 3 sections
    first_end    = int(max_chars * 0.40)
    middle_size  = int(max_chars * 0.35)
    last_size    = int(max_chars * 0.25)

    mid_start = (total_chars // 2) - (middle_size // 2)
    mid_end   = mid_start + middle_size

    truncated = (
        text[:first_end]
        + "\n\n[... section 1 ends — section 2 begins ...]\n\n"
        + text[mid_start:mid_end]
        + "\n\n[... section 2 ends — final section begins ...]\n\n"
        + text[-last_size:]
    )
    note = (
        f"Large document: {total_chars:,} chars across ~{total_pages} pages. "
        f"Analyzed beginning (40%), middle sample (35%), and end (25%)."
    )
    return truncated, note


# ── Detection ─────────────────────────────────────────────────────────────────

async def detect_contract_type(text: str, language: str) -> str:
    """Detect contract type. Always returns an English type string."""
    messages = [
        {
            "role": "user",
            "content": (
                f"This document is written in {language}.\n"
                "Identify the type of this document in English using 2-4 words.\n"
                "Choose the best match from:\n"
                "- house sale\n"
                "- car sale\n"
                "- lease agreement\n"
                "- employment\n"
                "- loan agreement\n"
                "- business partnership\n"
                "- service agreement\n"
                "- supply agreement\n"
                "- rental handbook\n"
                "- tenancy agreement\n"
                "If none match exactly, describe briefly in English.\n"
                "Return ONLY the document type, nothing else.\n\n"
                f"{text[:3000]}"
            )
        }
    ]
    try:
        contract_type = await chat(messages=messages, temperature=0.0)
        return contract_type.strip().lower()
    except Exception as e:
        print(f"[CONTRACT] Type detection failed: {e}")
        return "legal document"


# ── Safe Parsers ──────────────────────────────────────────────────────────────

def _safe_str(val) -> str:
    return str(val).strip() if val is not None else ""


def _safe_list(val) -> list:
    return val if isinstance(val, list) else []


def _parse_parties(raw: list) -> list[Party]:
    parties = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        try:
            parties.append(Party(
                name=_safe_str(p.get("name", "Unknown")),
                role=_safe_str(p.get("role", "")),
                obligations=[
                    _safe_str(o)
                    for o in _safe_list(p.get("obligations", []))
                    if o
                ]
            ))
        except Exception as e:
            print(f"[CONTRACT] Party parse error: {e}")
    return parties


def _parse_consequences(raw: list) -> list[Consequence]:
    consequences = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        try:
            severity = _safe_str(c.get("severity", "MEDIUM")).upper()
            if severity not in ("HIGH", "MEDIUM", "LOW"):
                severity = "MEDIUM"
            consequences.append(Consequence(
                trigger=_safe_str(c.get("trigger", "")),
                consequence=_safe_str(c.get("consequence", "")),
                severity=severity
            ))
        except Exception as e:
            print(f"[CONTRACT] Consequence parse error: {e}")
    return consequences


def _parse_risks(raw: list) -> list[RiskItem]:
    risks = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        try:
            level = _safe_str(r.get("risk_level", "MEDIUM")).upper()
            if level not in ("HIGH", "MEDIUM", "LOW"):
                level = "MEDIUM"
            risks.append(RiskItem(
                clause=_safe_str(r.get("clause", "")),
                risk_level=level,
                explanation=_safe_str(r.get("explanation", "")),
                recommendation=_safe_str(r.get("recommendation", ""))
            ))
        except Exception as e:
            print(f"[CONTRACT] Risk parse error: {e}")
    return risks


# ── Main Analysis ─────────────────────────────────────────────────────────────

async def analyze_contract(
    file_bytes: bytes,
    filename: str,
) -> ContractAnalysisResponse:

    # 1. Extract text
    print(f"[CONTRACT] Extracting text from: {filename}")
    full_text, total_pages = extract_text_from_pdf(file_bytes)

    if not full_text or len(full_text.strip()) < 50:
        raise ValueError(
            "Could not extract text from the uploaded document. "
            "Make sure the PDF contains selectable text and is not a scanned image."
        )

    print(f"[CONTRACT] Extracted: {total_pages} pages | {len(full_text):,} chars")

    # 2. Detect language from beginning of document
    print("[CONTRACT] Detecting language...")
    try:
        detected_language = await detect_language(full_text[:1000])
    except Exception as e:
        print(f"[CONTRACT] Language detection failed: {e} — defaulting to English")
        detected_language = "English"
    print(f"[CONTRACT] Language: {detected_language}")

    # 3. Detect contract type
    print("[CONTRACT] Detecting contract type...")
    contract_type = await detect_contract_type(full_text[:3000], detected_language)
    print(f"[CONTRACT] Type: {contract_type}")

    # 4. Smart truncation
    analysis_text, truncation_note = smart_truncate(
        text=full_text,
        total_pages=total_pages,
        max_chars=12000
    )
    if truncation_note:
        print(f"[CONTRACT] Truncation: {truncation_note}")
    else:
        print(f"[CONTRACT] No truncation needed")

    # 5. Build system prompt
    system_prompt = get_contract_analysis_prompt(contract_type, detected_language)

    # 6. Build user message
    user_content = "\n".join([
        f"Analyze this {contract_type} document thoroughly.",
        f"Document language: {detected_language}",
        f"Total pages in document: {total_pages}",
        f"Truncation note: {truncation_note}" if truncation_note else "",
        f"",
        f"CRITICAL: Your ENTIRE response must be in {detected_language}.",
        f"",
        f"DOCUMENT TEXT:",
        analysis_text
    ])

    messages = [{"role": "user", "content": user_content}]

    # 7. Call LLM
    print(f"[CONTRACT] Calling LLM: provider={settings.LLM_PROVIDER} "
          f"model={settings.OLLAMA_LLM_MODEL if settings.LLM_PROVIDER == 'ollama' else settings.GEMINI_LLM_MODEL}")

    try:
        result = await chat_json(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.1
        )
        print(f"[CONTRACT] LLM response OK — keys: {list(result.keys())}")
    except ValueError as e:
        print(f"[CONTRACT] LLM JSON error: {e}")
        raise ValueError(f"The AI model failed to return a structured analysis. "
                         f"Try a smaller document or switch LLM provider. Error: {str(e)}")
    except Exception as e:
        print(f"[CONTRACT] LLM call error: {type(e).__name__}: {e}")
        raise ValueError(f"LLM call failed: {type(e).__name__}: {str(e)}")

    # 8. Parse all fields safely
    risks        = _parse_risks(_safe_list(result.get("risks", [])))
    consequences = _parse_consequences(_safe_list(result.get("consequences", [])))
    parties      = _parse_parties(_safe_list(result.get("parties", [])))

    high   = sum(1 for r in risks if r.risk_level == "HIGH")
    medium = sum(1 for r in risks if r.risk_level == "MEDIUM")
    low    = sum(1 for r in risks if r.risk_level == "LOW")

    # Determine overall risk
    overall = _safe_str(result.get("overall_risk_level", "")).upper()
    if overall not in ("HIGH", "MEDIUM", "LOW"):
        if high >= 3:
            overall = "HIGH"
        elif high >= 1 or medium >= 3:
            overall = "MEDIUM"
        else:
            overall = "LOW"

    default_disclaimer = (
        "This is legal information only, not legal advice. "
        "Consult a qualified attorney for your specific situation."
    )

    print(f"[CONTRACT] Analysis complete — "
          f"{len(risks)} risks (H:{high} M:{medium} L:{low}) | "
          f"Overall: {overall}")

    return ContractAnalysisResponse(
        contract_type=_safe_str(
            result.get("contract_type", contract_type)
        ),
        detected_language=detected_language,
        summary=_safe_str(result.get("summary", "")),
        parties=parties,
        obligations=_safe_list(result.get("obligations", [])),
        limitations_and_restrictions=_safe_list(
            result.get("limitations_and_restrictions", [])
        ),
        requirements=_safe_list(result.get("requirements", [])),
        consequences=consequences,
        important_conditions=_safe_list(
            result.get("important_conditions", [])
        ),
        missing_clauses=_safe_list(result.get("missing_clauses", [])),
        risks=risks,
        high_count=high,
        medium_count=medium,
        low_count=low,
        total_risks=len(risks),
        overall_risk_level=overall,
        disclaimer=_safe_str(
            result.get("disclaimer", default_disclaimer)
        )
    )