from pydantic import BaseModel
from typing import Optional


ISSUE_CATEGORIES = [
    "Timeline Violation",
    "Transfer Restriction",
    "Financial Penalty",
    "Termination Liability",
    "Ambiguous Language",
    "Missing Clause",
    "Unfair Terms",
    "Legal Non-Compliance",
    "Payment Obligation",
    "Dispute Resolution",
    "Confidentiality Breach",
    "Intellectual Property",
    "Force Majeure",
    "Other"
]


class Party(BaseModel):
    name: str
    role: str
    obligations: list[str]


class Consequence(BaseModel):
    trigger: str
    consequence: str
    severity: str       # HIGH / MEDIUM / LOW


class RiskItem(BaseModel):
    clause: str
    risk_level: str                 # HIGH / MEDIUM / LOW
    issue_category: str             # Timeline Violation / Financial Penalty / etc.
    explanation: str
    recommendation: str


class IssueCategorySummary(BaseModel):
    category: str
    count: int
    risk_level: str     # highest risk level in this category


class ContractAnalysisResponse(BaseModel):
    # Basic info
    contract_type: str
    detected_language: str
    summary: str

    # Parties
    parties: list[Party] = []

    # Core analysis
    obligations: list[str] = []
    limitations_and_restrictions: list[str] = []
    requirements: list[str] = []
    consequences: list[Consequence] = []
    important_conditions: list[str] = []
    missing_clauses: list[str] = []

    # Risk assessment
    risks: list[RiskItem] = []
    issue_categories: list[IssueCategorySummary] = []  # ← new
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    total_risks: int = 0
    overall_risk_level: str = "UNKNOWN"

    disclaimer: str = (
        "This is legal information only, not legal advice. "
        "Consult a qualified attorney for your specific situation."
    )