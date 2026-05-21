from pydantic import BaseModel
from typing import Optional


class RegulationQueryRequest(BaseModel):
    question: str
    jurisdiction: str = "Ethiopia"
    context: Optional[str] = None   # optional extra context from user

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Can a landlord evict a tenant without notice in Addis Ababa?",
                "jurisdiction": "Ethiopia"
            }
        }
    }


class CitedSource(BaseModel):
    source: str
    article: str
    jurisdiction: str


class RegulationQueryResponse(BaseModel):
    answer: str
    sources: list[CitedSource]
    jurisdiction: str
    disclaimer: str = "This is legal information only, not legal advice. Consult a qualified attorney for your specific situation."