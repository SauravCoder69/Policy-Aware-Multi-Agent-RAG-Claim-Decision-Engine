"""Case Analysis Agent.

Parses input claim JSON, extracts structured facts, identifies missing/ambiguous evidence,
and creates a targeted policy investigation plan.
"""

from typing import Dict, Any, List
from app.graph.state import ClaimState


def run_case_analysis_agent(state: ClaimState) -> ClaimState:
    case_data = state.get("case_data", {})
    case_id = case_data.get("case_id", state.get("case_id", "UNKNOWN"))

    # Fact Extraction
    patient = case_data.get("patient", {})
    hospital = case_data.get("hospital", {})
    treatment = case_data.get("treatment", {})
    expenses = case_data.get("expenses_inr", {})
    documents = case_data.get("documents", [])
    evidence_ctx = case_data.get("evidence_context", {})
    expense_timing = case_data.get("expense_timing", {})
    prior_policy = case_data.get("prior_policy", {})

    case_facts = {
        "case_id": case_id,
        "policy_id": case_data.get("policy_id"),
        "policy_start_date": case_data.get("policy_start_date"),
        "claim_date": case_data.get("claim_date"),
        "sum_insured_inr": case_data.get("sum_insured_inr", 0),
        "continuous_coverage_months": case_data.get("continuous_coverage_months", 0),
        "prior_insurer_continuous_years": case_data.get("prior_insurer_continuous_years", 0),
        "patient_age": patient.get("age"),
        "hospital_name": hospital.get("name"),
        "network_provider": hospital.get("network_provider", False),
        "treatment_type": treatment.get("type"),
        "admission_hours": treatment.get("admission_hours", 0),
        "diagnosis": treatment.get("diagnosis", ""),
        "procedure": treatment.get("procedure", ""),
        "pre_existing": treatment.get("pre_existing", False),
        "experimental": treatment.get("experimental", False),
        "hospital_room_unavailable": treatment.get("hospital_room_unavailable", False),
        "patient_cannot_be_moved": treatment.get("patient_cannot_be_moved", False),
        "expenses": expenses,
        "documents": documents,
        "expense_timing": expense_timing,
        "prior_policy": prior_policy,
        "evidence_context": evidence_ctx,
        "task": case_data.get("task", "")
    }

    # Missing Evidence Identification
    missing_info = []
    if "hospital_registered" in evidence_ctx and evidence_ctx["hospital_registered"] is None:
        missing_info.append("hospital_registration_proof")
    if "medical_necessity_confirmed" in evidence_ctx and evidence_ctx["medical_necessity_confirmed"] is None:
        missing_info.append("medical_necessity_certificate")
    if "hospital_minimum_criteria_documented" in evidence_ctx and evidence_ctx["hospital_minimum_criteria_documented"] is False:
        missing_info.append("hospital_minimum_criteria_documentation")
    if not documents or "itemized_bill" not in documents:
        missing_info.append("itemized_hospital_bill")

    case_facts["missing_facts"] = missing_info

    # Investigation Plan Formulation
    investigation_plan: List[Dict[str, Any]] = [
        {
            "dimension": "coverage_scope",
            "query": f"scope of cover inpatient hospitalization {treatment.get('diagnosis', '')}"
        },
        {
            "dimension": "waiting_period",
            "query": "thirty 30 days initial waiting period illness coverage inception"
        },
        {
            "dimension": "pre_existing_disease",
            "query": "pre existing disease condition waiting period 48 months four years"
        },
        {
            "dimension": "exclusions",
            "query": f"exclusions cosmetic surgery experimental unproven treatment {treatment.get('procedure', '')}"
        },
        {
            "dimension": "domiciliary_treatment",
            "query": "domiciliary hospitalization treatment room unavailable patient cannot be moved sub limit"
        },
        {
            "dimension": "day_care",
            "query": "day care treatment 24 hours procedure local anesthesia cataract eye surgery"
        },
        {
            "dimension": "limits_and_sublimits",
            "query": "room rent limit ICU category limit cataract limit ambulance sub limit"
        },
        {
            "dimension": "pre_post_hospitalization",
            "query": "pre hospitalization 30 days post hospitalization 60 days expenses timing"
        },
        {
            "dimension": "hospital_definition",
            "query": "definition of hospital nursing home registration 10 15 beds qualified doctor nursing staff"
        },
        {
            "dimension": "portability",
            "query": "portability credit continuous coverage previous insurer indian health insurance"
        }
    ]

    state["case_facts"] = case_facts
    state["investigation_plan"] = investigation_plan
    
    trace_msg = f"[CaseAnalysisAgent] Extracted facts for case {case_id}. Identified {len(missing_info)} evidence gaps and generated {len(investigation_plan)} investigation queries."
    trace = state.get("trace", [])
    trace.append(trace_msg)
    state["trace"] = trace

    return state
