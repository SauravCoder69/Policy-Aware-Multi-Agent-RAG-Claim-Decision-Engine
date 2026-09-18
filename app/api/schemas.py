"""API Schemas."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    vectorstore_indexed: bool
    bm25_indexed: bool


class AnalysisResponse(BaseModel):
    case_id: str
    decision: str
    confidence: float
    summary: str
    key_findings: List[Dict[str, Any]]
    applicable_limits: List[Dict[str, Any]]
    missing_evidence: List[str]
    citations: List[Dict[str, Any]]
    validation: Dict[str, Any]
    trace: List[str]
