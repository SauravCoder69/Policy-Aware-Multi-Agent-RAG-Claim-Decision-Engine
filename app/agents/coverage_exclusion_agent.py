"""Coverage & Exclusion Agent.

Compares extracted claim facts against retrieved policy evidence chunks to evaluate
eligibility, exclusions, waiting periods, sub-limits, and evidence gaps.
"""

from typing import Dict, Any, List
from app.graph.state import ClaimState


def find_matching_chunks(evidence: List[Dict[str, Any]], keywords: List[str]) -> List[str]:
    """Find chunk_ids matching any of the given keywords."""
    matched_ids = []
    for chunk in evidence:
        text = chunk.get("text", "").lower()
        heading = chunk.get("heading", "").lower()
        section = chunk.get("section", "").lower()
        full_str = f"{text} {heading} {section}"
        if any(kw.lower() in full_str for kw in keywords):
            matched_ids.append(chunk["chunk_id"])
    return matched_ids[:3]


def extract_percentage_from_chunks(evidence: List[Dict[str, Any]], keywords: List[str], default_percent: float) -> float:
    """Extract percentage value from evidence chunks matching keywords."""
    import re
    for chunk in evidence:
        text = chunk.get("text", "").lower()
        heading = chunk.get("heading", "").lower()
        section = chunk.get("section", "").lower()
        full_str = f"{text} {heading} {section}"
        if any(kw.lower() in full_str for kw in keywords):
            # Look for percentage patterns like "20%", "20 percent", "1%"
            percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%?\s*(?:percent|of)', full_str)
            if percent_match:
                try:
                    return float(percent_match.group(1)) / 100.0
                except (ValueError, IndexError):
                    pass
    return default_percent


def extract_absolute_limit_from_chunks(evidence: List[Dict[str, Any]], keywords: List[str], default_limit: float) -> float:
    """Extract absolute limit value from evidence chunks matching keywords."""
    import re
    for chunk in evidence:
        text = chunk.get("text", "").lower()
        heading = chunk.get("heading", "").lower()
        section = chunk.get("section", "").lower()
        full_str = f"{text} {heading} {section}"
        if any(kw.lower() in full_str for kw in keywords):
            # Look for currency patterns like "INR 25000", "Rs. 25000", "25,000"
            limit_match = re.search(r'(?:inr|rs\.?|₹)\s*[\d,]+', full_str)
            if limit_match:
                try:
                    return float(limit_match.group(0).replace(',', '').replace('inr', '').replace('rs.', '').replace('₹', '').strip())
                except (ValueError, IndexError):
                    pass
    return default_limit


def run_coverage_exclusion_agent(state: ClaimState) -> ClaimState:
    case_facts = state.get("case_facts", {})
    evidence = state.get("retrieved_evidence", [])

    coverage_findings: List[Dict[str, Any]] = []
    applicable_limits: List[Dict[str, Any]] = []
    missing_evidence: List[str] = list(case_facts.get("missing_facts", []))

    treatment_type = case_facts.get("treatment_type", "inpatient")
    diagnosis = case_facts.get("diagnosis", "").lower()
    procedure = case_facts.get("procedure", "").lower()
    pre_existing = case_facts.get("pre_existing", False)
    experimental = case_facts.get("experimental", False)
    continuous_months = case_facts.get("continuous_coverage_months", 0)
    prior_years = case_facts.get("prior_insurer_continuous_years", 0)
    sum_insured = case_facts.get("sum_insured_inr", 500000)
    expenses = case_facts.get("expenses", {})
    evidence_ctx = case_facts.get("evidence_context", {})
    expense_timing = case_facts.get("expense_timing", {})
    prior_policy = case_facts.get("prior_policy", {})

    # 1. Initial 30-Day Waiting Period Analysis
    if continuous_months == 0 and prior_years == 0:
        wp_chunks = find_matching_chunks(evidence, ["30 days", "thirty days", "waiting period", "inception"])
        coverage_findings.append({
            "dimension": "waiting_period",
            "finding": "The claim falls within the initial 30-day waiting period from policy inception for non-accidental illness.",
            "is_restriction": True,
            "evidence_refs": wp_chunks or [evidence[0]["chunk_id"]] if evidence else []
        })

    # 2. Pre-Existing Disease (PED) Analysis
    if pre_existing:
        ped_chunks = find_matching_chunks(evidence, ["pre-existing", "pre existing", "48 months", "four years"])
        if prior_policy.get("continuous_years", 0) > 0:
            # Portability credit applies
            coverage_findings.append({
                "dimension": "portability_credit",
                "finding": f"Patient has {prior_policy.get('continuous_years')} year(s) prior continuous coverage. Portability rules credit prior tenure against waiting periods.",
                "is_restriction": False,
                "evidence_refs": ped_chunks or [evidence[0]["chunk_id"]] if evidence else []
            })
        elif continuous_months < 48:
            coverage_findings.append({
                "dimension": "pre_existing_disease",
                "finding": f"Pre-existing disease condition management claimed at {continuous_months} months continuous coverage, which is within the policy's 48-month PED waiting period.",
                "is_restriction": True,
                "evidence_refs": ped_chunks or [evidence[0]["chunk_id"]] if evidence else []
            })
        else:
            coverage_findings.append({
                "dimension": "pre_existing_disease",
                "finding": f"Pre-existing disease waiting period satisfied as continuous coverage ({continuous_months} months) exceeds 48 months.",
                "is_restriction": False,
                "evidence_refs": ped_chunks or [evidence[0]["chunk_id"]] if evidence else []
            })

    # 3. Exclusions Analysis
    if experimental or "experimental" in diagnosis or "experimental" in procedure or "stem cell" in procedure:
        excl_chunks = find_matching_chunks(evidence, ["experimental", "unproven", "exclusion"])
        coverage_findings.append({
            "dimension": "exclusions",
            "finding": "Treatment is excluded under policy Section 3 as experimental or unproven therapy.",
            "is_restriction": True,
            "evidence_refs": excl_chunks or [evidence[0]["chunk_id"]] if evidence else []
        })

    if any(k in diagnosis or k in procedure for k in ["cosmetic", "rhinoplasty", "aesthetic", "plastic surgery"]):
        excl_chunks = find_matching_chunks(evidence, ["cosmetic", "aesthetic", "exclusion"])
        coverage_findings.append({
            "dimension": "exclusions",
            "finding": "Cosmetic surgery / elective aesthetic treatment is specifically excluded under policy Section 3.",
            "is_restriction": True,
            "evidence_refs": excl_chunks or [evidence[0]["chunk_id"]] if evidence else []
        })

    # 4. Domiciliary Hospitalization
    if treatment_type == "domiciliary":
        dom_chunks = find_matching_chunks(evidence, ["domiciliary", "home", "20%"])
        room_unavail = case_facts.get("hospital_room_unavailable", False)
        cannot_move = case_facts.get("patient_cannot_be_moved", False)

        if room_unavail or cannot_move:
            domiciliary_percent = extract_percentage_from_chunks(evidence, ["domiciliary", "20%", "sub limit"], 0.20)
            coverage_findings.append({
                "dimension": "domiciliary_treatment",
                "finding": f"Domiciliary treatment satisfies policy conditions (hospital room unavailable / patient cannot be moved). Covered subject to {domiciliary_percent*100:.0f}% domiciliary sub-limit of Sum Insured.",
                "is_restriction": False,
                "evidence_refs": dom_chunks or [evidence[0]["chunk_id"]] if evidence else []
            })
            sublimit = sum_insured * domiciliary_percent
            applicable_limits.append({
                "category": "domiciliary_sublimit",
                "limit_amount_inr": sublimit,
                "description": f"Domiciliary hospitalization sub-limit capped at {domiciliary_percent*100:.0f}% of Sum Insured (INR {sublimit:,.0f}).",
                "evidence_refs": dom_chunks or []
            })
        else:
            coverage_findings.append({
                "dimension": "domiciliary_treatment",
                "finding": "Domiciliary treatment criteria not satisfied as neither hospital room unavailability nor inability to move patient was documented.",
                "is_restriction": True,
                "evidence_refs": dom_chunks or []
            })

    # 5. Day Care Treatment
    if treatment_type == "day_care":
        dc_chunks = find_matching_chunks(evidence, ["day care", "24 hours", "cataract"])
        coverage_findings.append({
            "dimension": "day_care",
            "finding": f"Procedure '{case_facts.get('procedure')}' qualifies for day-care treatment (less than 24 hours hospitalization under local/general anesthesia).",
            "is_restriction": False,
            "evidence_refs": dc_chunks or [evidence[0]["chunk_id"]] if evidence else []
        })
        if "cataract" in diagnosis or "cataract" in procedure or "eye" in procedure:
            cataract_percent = extract_percentage_from_chunks(evidence, ["cataract", "10%", "limit"], 0.10)
            cataract_absolute = extract_absolute_limit_from_chunks(evidence, ["cataract", "25000", "inr"], 25000)
            cat_limit = min(cataract_absolute, sum_insured * cataract_percent)
            applicable_limits.append({
                "category": "cataract_sublimit",
                "limit_amount_inr": cat_limit,
                "description": f"Cataract surgery sub-limit capped at INR {cataract_absolute:,.0f} or {cataract_percent*100:.0f}% of Sum Insured per eye as per policy terms.",
                "evidence_refs": dc_chunks or []
            })

    # 6. Category Sub-Limits & Room Rent Caps
    room_expense = expenses.get("room", 0)
    if room_expense > 0:
        room_chunks = find_matching_chunks(evidence, ["room rent", "icu", "1%", "2%"])
        room_percent = extract_percentage_from_chunks(evidence, ["room rent", "1%", "per day"], 0.01)
        room_limit_per_day = sum_insured * room_percent
        applicable_limits.append({
            "category": "room_rent_limit",
            "limit_amount_inr": room_limit_per_day,
            "description": f"Room rent limit capped at {room_percent*100:.0f}% of Sum Insured (INR {room_limit_per_day:,.0f} per day).",
            "evidence_refs": room_chunks or []
        })

    if "cancer" in diagnosis:
        cat_chunks = find_matching_chunks(evidence, ["major illness", "cancer", "category limit"])
        applicable_limits.append({
            "category": "cancer_treatment_limit",
            "limit_amount_inr": sum_insured,
            "description": "Cancer treatment covered up to the Sum Insured subject to itemized medical necessity.",
            "evidence_refs": cat_chunks or []
        })

    # 7. Pre / Post Hospitalization Time Windows
    if expense_timing:
        pre_days = expense_timing.get("pre_hospitalization_days_before_admission", 0)
        post_days = expense_timing.get("post_hospitalization_days_after_discharge", 0)
        time_chunks = find_matching_chunks(evidence, ["pre hospitalization", "post hospitalization", "30 days", "60 days"])
        if pre_days <= 30 and post_days <= 60:
            coverage_findings.append({
                "dimension": "expense_timing",
                "finding": f"Pre-hospitalization ({pre_days} days) and post-hospitalization ({post_days} days) expenses fall within the policy allowed windows (30 days pre / 60 days post).",
                "is_restriction": False,
                "evidence_refs": time_chunks or []
            })
        else:
            coverage_findings.append({
                "dimension": "expense_timing",
                "finding": f"Pre-hospitalization or post-hospitalization expenses exceed the policy windows (30 days pre / 60 days post).",
                "is_restriction": True,
                "evidence_refs": time_chunks or []
            })

    # 8. Evidence Gaps & Mandatory Abstention Triggers
    if "hospital_registered" in evidence_ctx and evidence_ctx["hospital_registered"] is None:
        if "hospital_registration_proof" not in missing_evidence:
            missing_evidence.append("hospital_registration_proof")
        coverage_findings.append({
            "dimension": "hospital_definition",
            "finding": "Supplied evidence does not establish whether facility meets policy definition of a registered Hospital.",
            "is_restriction": True,
            "evidence_refs": find_matching_chunks(evidence, ["hospital", "nursing home", "definition"]) or []
        })

    if "hospital_minimum_criteria_documented" in evidence_ctx and evidence_ctx["hospital_minimum_criteria_documented"] is False:
        if "hospital_minimum_criteria_documentation" not in missing_evidence:
            missing_evidence.append("hospital_minimum_criteria_documentation")
        coverage_findings.append({
            "dimension": "hospital_definition",
            "finding": "Facility fails to document minimum hospital criteria (10-15 beds, OT, 24/7 medical staff).",
            "is_restriction": True,
            "evidence_refs": find_matching_chunks(evidence, ["hospital", "10 beds", "15 beds"]) or []
        })

    state["coverage_findings"] = coverage_findings
    state["case_facts"]["applicable_limits"] = applicable_limits
    state["case_facts"]["missing_facts"] = missing_evidence

    trace_msg = f"[CoverageExclusionAgent] Evaluated claim. Generated {len(coverage_findings)} coverage findings and {len(applicable_limits)} applicable policy limits."
    trace = state.get("trace", [])
    trace.append(trace_msg)
    state["trace"] = trace

    return state
