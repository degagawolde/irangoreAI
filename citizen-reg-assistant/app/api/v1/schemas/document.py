from pydantic import BaseModel
from typing import Optional


class Party(BaseModel):
    name: str
    role: str
    obligations: list[str]


class Consequence(BaseModel):
    trigger: str        # what causes it
    consequence: str    # what happens
    severity: str       # HIGH / MEDIUM / LOW


class RiskItem(BaseModel):
    clause: str
    risk_level: str
    explanation: str
    recommendation: str


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
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    total_risks: int = 0

    # Metadata
    overall_risk_level: str = "UNKNOWN"   # HIGH / MEDIUM / LOW
    disclaimer: str = (
        "This is legal information only, not legal advice. "
        "Consult a qualified attorney for your specific situation."
    )