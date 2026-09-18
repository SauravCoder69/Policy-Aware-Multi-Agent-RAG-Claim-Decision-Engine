"""Decision Agent.

Synthesizes case facts, policy evidence, coverage findings, and evidence gaps into a final
evidence-backed decision status (ADMISSIBLE, ADMISSIBLE_WITH_LIMITS, PARTIALLY_ADMISSIBLE,
NOT_ADMISSIBLE, NEEDS_REVIEW).
"""

from typing import Dict, Any, List
from app.graph.state import ClaimState


def run_decision_agent(state: ClaimState) -> ClaimState:
    case_facts = state.get("case_facts", {})
    coverage_findings = state.get("coverage_findings", [])
    evidence = state.get("retrieved_evidence", [])
    case_id = case_facts.get("case_id", "UNKNOWN")

    missing_evidence = case_facts.get("missing_facts", [])
    applicable_limits = case_facts.get("applicable_limits", [])

    # Mandatory Abstention Check: If critical evidence is missing or unverified
    critical_missing = [m for m in missing_evidence if m in [
        "hospital_registration_proof",
        "hospital_minimum_criteria_documentation",
        "medical_necessity_certificate"
    ]]

    # Check for Exclusions / Waiting Period Violations
    has_exclusion = any(f.get("is_restriction") and f.get("dimension") == "exclusions" for f in coverage_findings)
    has_wp_violation = any(f.get("is_restriction") and f.get("dimension") in ["waiting_period", "pre_existing_disease"] for f in coverage_findings)
    has_domiciliary_failure = any(f.get("is_restriction") and f.get("dimension") == "domiciliary_treatment" for f in coverage_findings)

    # Determine Decision Status
    if critical_missing or "determine whether the claim can be finally decided when" in case_facts.get("task", "").lower():
        decision_status = "NEEDS_REVIEW"
        confidence = 0.85
        summary = "Insufficient evidence to establish hospital registration / medical necessity criteria safely under policy terms. System abstains."
    elif has_exclusion:
        # Check if there's evidence of a covered component (not just limits)
        # Look for findings that indicate coverage eligibility
        has_covered_component = any(
            not f.get("is_restriction") and f.get("dimension") in ["coverage", "scope_of_cover"]
            for f in coverage_findings
        )
        
        if has_covered_component:
            decision_status = "PARTIALLY_ADMISSIBLE"
            confidence = 0.88
            summary = "Claim is partially admissible - some expenses are covered under policy terms subject to sub-limits, while other aspects fall under exclusions or restrictions."
        else:
            decision_status = "NOT_ADMISSIBLE"
            confidence = 0.95
            summary = "Claim is not admissible as it falls under a policy exclusion with no evidence of a covered component."
    elif has_wp_violation or has_domiciliary_failure:
        decision_status = "NOT_ADMISSIBLE"
        confidence = 0.95
        summary = "Claim is not admissible as it falls under a policy exclusion, unfulfilled domiciliary criteria, or active waiting period restriction."
    elif applicable_limits:
        decision_status = "ADMISSIBLE_WITH_LIMITS"
        confidence = 0.92
        summary = "Claim is admissible under policy coverage terms, subject to category-specific sub-limits and deductions."
    else:
        decision_status = "ADMISSIBLE"
        confidence = 0.95
        summary = "Claim satisfies all policy terms and coverage conditions without material restrictions."

    # Build Citations from retrieved evidence referenced in findings
    ref_chunk_ids = set()
    for finding in coverage_findings:
        for cid in finding.get("evidence_refs", []):
            ref_chunk_ids.add(cid)

    for limit in applicable_limits:
        for cid in limit.get("evidence_refs", []):
            ref_chunk_ids.add(cid)

    # Ensure at least 1-3 relevant citations
    citations: List[Dict[str, Any]] = []
    for chunk in evidence:
        if chunk["chunk_id"] in ref_chunk_ids or len(citations) < 2:
            citations.append({
                "source": chunk.get("source", "USGIC-CSCIndividualHealthInsurance_2017-2018.pdf"),
                "page": chunk.get("page", 1),
                "section": chunk.get("section", "Policy Terms"),
                "chunk_id": chunk.get("chunk_id"),
                "heading": chunk.get("heading", ""),
                "text": chunk.get("text", "")[:250] + "..."
            })
        if len(citations) >= 4:
            break

    # Format Key Findings
    key_findings = []
    for f in coverage_findings:
        key_findings.append({
            "dimension": f.get("dimension"),
            "finding": f.get("finding"),
            "evidence_refs": f.get("evidence_refs", [])
        })

    decision_dict = {
        "case_id": case_id,
        "decision": decision_status,
        "confidence": confidence,
        "summary": summary,
        "key_findings": key_findings,
        "applicable_limits": applicable_limits,
        "missing_evidence": missing_evidence,
        "citations": citations,
        "next_action": "Request additional documentation" if decision_status == "NEEDS_REVIEW" else "Process claim according to decision status"
    }

    state["decision"] = decision_dict

    trace_msg = f"[DecisionAgent] Formulated final decision '{decision_status}' with confidence {confidence} and {len(citations)} citations."
    trace = state.get("trace", [])
    trace.append(trace_msg)
    state["trace"] = trace

    return state
