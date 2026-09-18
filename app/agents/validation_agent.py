"""Validation Agent.

Audits the decision output for citation validity, page/section accuracy,
unsupported policy claims, and abstention compliance.
"""

from typing import Dict, Any, List
from app.graph.state import ClaimState


def run_validation_agent(state: ClaimState) -> ClaimState:
    decision = state.get("decision", {})
    evidence = state.get("retrieved_evidence", [])
    revision_count = state.get("revision_count", 0)

    unsupported_claims: List[str] = []
    citation_errors: List[str] = []

    valid_chunk_ids = {c["chunk_id"]: c for c in evidence}

    # 1. Audit Citations
    citations = decision.get("citations", [])
    if not citations and decision.get("decision") != "NEEDS_REVIEW":
        citation_errors.append("Decision lacks citations to policy evidence.")

    for cit in citations:
        cid = cit.get("chunk_id")
        if cid not in valid_chunk_ids:
            citation_errors.append(f"Citation chunk_id '{cid}' not found in retrieved policy evidence.")
        else:
            orig = valid_chunk_ids[cid]
            if cit.get("page") != orig.get("page"):
                citation_errors.append(f"Citation page mismatch for chunk '{cid}': expected {orig.get('page')}, got {cit.get('page')}.")

    # 2. Audit Findings for Evidence Support
    key_findings = decision.get("key_findings", [])
    for finding in key_findings:
        refs = finding.get("evidence_refs", [])
        if not refs and decision.get("decision") != "NEEDS_REVIEW":
            unsupported_claims.append(f"Finding '{finding.get('dimension')}' has no evidence references.")

    # 3. Audit Abstention Rule Compliance
    missing_evidence = decision.get("missing_evidence", [])
    critical_missing = [m for m in missing_evidence if m in [
        "hospital_registration_proof",
        "hospital_minimum_criteria_documentation",
        "medical_necessity_certificate"
    ]]
    if critical_missing and decision.get("decision") != "NEEDS_REVIEW":
        unsupported_claims.append(f"Critical evidence missing ({critical_missing}) but decision status is '{decision.get('decision')}' instead of 'NEEDS_REVIEW'.")

    # Determine PASS / FAIL status
    has_errors = bool(unsupported_claims or citation_errors)
    revision_required = has_errors and (revision_count < 2)

    if has_errors and not revision_required:
        # Force NEEDS_REVIEW if revision limit reached and errors persist
        decision["decision"] = "NEEDS_REVIEW"
        decision["summary"] = "Validation audit failed to confirm citations; system safely abstains to NEEDS_REVIEW."

    validation_result = {
        "status": "FAIL" if has_errors else "PASS",
        "unsupported_claims": unsupported_claims,
        "citation_errors": citation_errors,
        "revision_required": revision_required
    }

    state["validation"] = validation_result
    state["decision"] = decision

    trace_msg = f"[ValidationAgent] Audit completed. Status: {validation_result['status']} (Unsupported Claims: {len(unsupported_claims)}, Citation Errors: {len(citation_errors)})."
    trace = state.get("trace", [])
    trace.append(trace_msg)
    state["trace"] = trace

    return state
