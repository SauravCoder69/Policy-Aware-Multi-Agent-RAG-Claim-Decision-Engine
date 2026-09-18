"""LangGraph State Machine Workflow.

Orchestrates the 5 specialized agents in sequence with a conditional validation loop.
"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.graph.state import ClaimState
from app.agents.case_analysis_agent import run_case_analysis_agent
from app.agents.policy_evidence_agent import run_policy_evidence_agent
from app.agents.coverage_exclusion_agent import run_coverage_exclusion_agent
from app.agents.decision_agent import run_decision_agent
from app.agents.validation_agent import run_validation_agent
from app.config import settings


def should_revise(state: ClaimState) -> str:
    """Conditional routing after Validation Agent audit."""
    validation = state.get("validation", {})
    revision_count = state.get("revision_count", 0)

    if validation.get("revision_required") and revision_count < settings.REVISION_LIMIT:
        state["revision_count"] = revision_count + 1
        trace = state.get("trace", [])
        trace.append(f"[WorkflowLoop] Validation failed. Triggering controlled revision {state['revision_count']}/{settings.REVISION_LIMIT}.")
        state["trace"] = trace
        return "decision_agent"
    return END


def create_claim_analyzer_workflow():
    """Build and compile the LangGraph workflow graph."""
    workflow = StateGraph(ClaimState)

    # Add 5 specialized agent nodes
    workflow.add_node("case_analysis_agent", run_case_analysis_agent)
    workflow.add_node("policy_evidence_agent", run_policy_evidence_agent)
    workflow.add_node("coverage_exclusion_agent", run_coverage_exclusion_agent)
    workflow.add_node("decision_agent", run_decision_agent)
    workflow.add_node("validation_agent", run_validation_agent)

    # Define standard execution sequence
    workflow.set_entry_point("case_analysis_agent")
    workflow.add_edge("case_analysis_agent", "policy_evidence_agent")
    workflow.add_edge("policy_evidence_agent", "coverage_exclusion_agent")
    workflow.add_edge("coverage_exclusion_agent", "decision_agent")
    workflow.add_edge("decision_agent", "validation_agent")

    # Conditional edge from validation
    workflow.add_conditional_edges(
        "validation_agent",
        should_revise,
        {
            "decision_agent": "decision_agent",
            END: END
        }
    )

    return workflow.compile()


class ClaimAnalyzerRunner:
    def __init__(self):
        self.app = create_claim_analyzer_workflow()

    def run_analysis(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        initial_state: ClaimState = {
            "case_id": case_data.get("case_id", "UNKNOWN"),
            "case_data": case_data,
            "case_facts": {},
            "investigation_plan": [],
            "retrieved_evidence": [],
            "coverage_findings": [],
            "decision": {},
            "validation": {},
            "trace": [f"[WorkflowStart] Initiating analysis for claim case {case_data.get('case_id')}."],
            "revision_count": 0
        }

        final_state = self.app.invoke(initial_state)

        # Assemble clean API output response matching specification
        decision = final_state.get("decision", {})
        validation = final_state.get("validation", {})
        trace = final_state.get("trace", [])

        return {
            "case_id": final_state.get("case_id"),
            "decision": decision.get("decision", "NEEDS_REVIEW"),
            "confidence": decision.get("confidence", 0.0),
            "summary": decision.get("summary", ""),
            "key_findings": decision.get("key_findings", []),
            "applicable_limits": decision.get("applicable_limits", []),
            "missing_evidence": decision.get("missing_evidence", []),
            "citations": decision.get("citations", []),
            "validation": validation,
            "trace": trace
        }


runner = ClaimAnalyzerRunner()


def run_claim_analysis(case_data: Dict[str, Any]) -> Dict[str, Any]:
    return runner.run_analysis(case_data)
