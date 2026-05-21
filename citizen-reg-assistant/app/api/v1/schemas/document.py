from pydantic import BaseModel


class RiskItem(BaseModel):
    clause: str
    risk_level: str
    explanation: str
    recommendation: str


class DocumentRiskResponse(BaseModel):
    contract_type: str = "unknown"
    detected_language: str = "English"
    summary: str
    missing_clauses: list[str] = []
    risks: list[RiskItem]
    total_risks: int
    high_count: int
    medium_count: int
    low_count: int
    disclaimer: str = (
        "This is legal information only, not legal advice. "
        "Consult a qualified attorney for your specific situation."
    )