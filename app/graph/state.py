"""Structured Workflow State Definition."""

from typing import Any, Dict, List, TypedDict


class ClaimState(TypedDict):
    case_id: str
    case_data: Dict[str, Any]
    case_facts: Dict[str, Any]
    investigation_plan: List[Dict[str, Any]]
    retrieved_evidence: List[Dict[str, Any]]
    coverage_findings: List[Dict[str, Any]]
    decision: Dict[str, Any]
    validation: Dict[str, Any]
    trace: List[str]
    revision_count: int
