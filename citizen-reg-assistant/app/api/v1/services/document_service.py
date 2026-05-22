import re
from app.core.config import settings
from app.api.v1.services.llm_service import chat, chat_json, detect_language
from app.api.v1.helpers.pdf_parser import (
    extract_text_with_ocr_fallback,
    smart_truncate
)
from app.api.v1.schemas.document import (
    ContractAnalysisResponse,
    Party,
    Consequence,
    RiskItem,
    IssueCategorySummary,
    ISSUE_CATEGORIES
)
from app.core.prompts import get_contract_analysis_prompt


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
                "If none match, describe briefly in English.\n"
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


def _normalize_category(raw: str) -> str:
    """Match raw LLM category to known categories. Fallback to Other."""
    if not raw:
        return "Other"
    raw_clean = raw.strip()

    # Exact match
    if raw_clean in ISSUE_CATEGORIES:
        return raw_clean

    # Case-insensitive match
    for cat in ISSUE_CATEGORIES:
        if cat.lower() == raw_clean.lower():
            return cat

    # Partial match
    for cat in ISSUE_CATEGORIES:
        if (cat.lower() in raw_clean.lower()
                or raw_clean.lower() in cat.lower()):
            return cat

    return "Other"


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
                issue_category=_normalize_category(
                    _safe_str(r.get("issue_category", "Other"))
                ),
                explanation=_safe_str(r.get("explanation", "")),
                recommendation=_safe_str(r.get("recommendation", ""))
            ))
        except Exception as e:
            print(f"[CONTRACT] Risk parse error: {e}")
    return risks


def _build_issue_summary(
    risks: list[RiskItem]
) -> list[IssueCategorySummary]:
    """
    Build a ranked summary of risk categories.
    Sorted by severity then count.
    """
    category_map: dict[str, list[str]] = {}
    for risk in risks:
        cat = risk.issue_category
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(risk.risk_level)

    severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    summary = []
    for cat, levels in sorted(category_map.items()):
        highest = max(levels, key=lambda x: severity_order.get(x, 0))
        summary.append(IssueCategorySummary(
            category=cat,
            count=len(levels),
            risk_level=highest
        ))

    summary.sort(
        key=lambda x: (severity_order.get(x.risk_level, 0), x.count),
        reverse=True
    )
    return summary


# ── Main Analysis ─────────────────────────────────────────────────────────────

async def analyze_contract(
    file_bytes: bytes,
    filename: str,
) -> ContractAnalysisResponse:

    # 1. Extract text — OCR fallback for scanned PDFs
    print(f"[CONTRACT] ── Starting analysis: {filename} ──")
    full_text, total_pages, ocr_used = await extract_text_with_ocr_fallback(
        file_bytes=file_bytes,
        filename=filename
    )

    print(
        f"[CONTRACT] Extraction complete — "
        f"{total_pages} pages | {len(full_text):,} chars | "
        f"OCR: {ocr_used}"
    )

    # 2. Detect language
    print("[CONTRACT] Detecting language...")
    try:
        detected_language = await detect_language(full_text[:1000])
    except Exception as e:
        print(f"[CONTRACT] Language detection failed: {e} — defaulting to English")
        detected_language = "English"
    print(f"[CONTRACT] Language: {detected_language}")

    # 3. Detect contract type
    print("[CONTRACT] Detecting contract type...")
    contract_type = await detect_contract_type(
        full_text[:3000], detected_language
    )
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

    # 5. Build prompt
    system_prompt = get_contract_analysis_prompt(
        contract_type, detected_language
    )

    # 6. Build user message
    user_content = "\n".join(filter(None, [
        f"Analyze this {contract_type} document thoroughly.",
        f"Document language: {detected_language}",
        f"Total pages: {total_pages}",
        f"OCR extraction was used: {ocr_used}",
        f"Note: {truncation_note}" if truncation_note else "",
        "",
        f"CRITICAL: Your ENTIRE response must be in {detected_language}.",
        "Assign an issue_category in English to every risk item.",
        "",
        "DOCUMENT TEXT:",
        analysis_text
    ]))

    messages = [{"role": "user", "content": user_content}]

    # 7. Call LLM
    llm_model = (
        settings.GEMINI_LLM_MODEL
        if settings.LLM_PROVIDER == "gemini"
        else settings.OLLAMA_LLM_MODEL
    )
    print(
        f"[CONTRACT] Calling LLM: "
        f"provider={settings.LLM_PROVIDER} | model={llm_model}"
    )

    try:
        result = await chat_json(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.1
        )
        print(f"[CONTRACT] LLM OK — keys: {list(result.keys())}")
    except ValueError as e:
        print(f"[CONTRACT] LLM JSON error: {e}")
        raise ValueError(
            "The AI model failed to return a structured analysis. "
            f"Error: {str(e)}"
        )
    except Exception as e:
        print(f"[CONTRACT] LLM error: {type(e).__name__}: {e}")
        raise ValueError(f"LLM call failed: {type(e).__name__}: {str(e)}")

    # 8. Parse all fields safely
    risks            = _parse_risks(_safe_list(result.get("risks", [])))
    consequences     = _parse_consequences(
        _safe_list(result.get("consequences", []))
    )
    parties          = _parse_parties(_safe_list(result.get("parties", [])))
    issue_categories = _build_issue_summary(risks)

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

    print(
        f"[CONTRACT] ── Analysis complete ──\n"
        f"  Risks      : {len(risks)} total "
        f"(H:{high} M:{medium} L:{low})\n"
        f"  Overall    : {overall}\n"
        f"  OCR used   : {ocr_used}\n"
        f"  Categories : "
        f"{[f'{c.category}({c.count})' for c in issue_categories]}"
    )

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
        issue_categories=issue_categories,
        high_count=high,
        medium_count=medium,
        low_count=low,
        total_risks=len(risks),
        overall_risk_level=overall,
        disclaimer=_safe_str(
            result.get("disclaimer", default_disclaimer)
        )
    )