"""Streamlit Frontend Application.

Interactive reviewer dashboard for health insurance claim evaluation, displaying
evidence-backed decision badges, findings, sub-limits, citations, validation audit, and trace logs.
"""

import sys
import os
import json
import streamlit as st

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.graph.workflow import run_claim_analysis
from app.config import settings

st.set_page_config(
    page_title="Aptino Health Claim Analyzer",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Aptino AI Engineer — Health Insurance Claim Analyzer")
st.markdown("Evidence-backed automated health claim decision system powered by **RAG** and a **5-Agent LangGraph Workflow**.")


@st.cache_data
def load_all_test_cases():
    cases = {}
    if os.path.exists(settings.PUBLIC_CASES_PATH):
        with open(settings.PUBLIC_CASES_PATH, "r", encoding="utf-8") as f:
            for c in json.load(f):
                cases[f"Public: {c['case_id']} - {c['treatment'].get('diagnosis', 'Claim')}"] = c
    if os.path.exists(settings.CUSTOM_CASES_PATH):
        with open(settings.CUSTOM_CASES_PATH, "r", encoding="utf-8") as f:
            for c in json.load(f):
                cases[f"Custom: {c['case_id']} - {c['treatment'].get('diagnosis', 'Claim')}"] = c
    return cases


cases_dict = load_all_test_cases()

st.sidebar.header("📋 Select Claim Case")
selected_case_name = st.sidebar.selectbox("Choose a test case:", list(cases_dict.keys()))
default_json_str = json.dumps(cases_dict[selected_case_name], indent=2)

st.sidebar.markdown("---")
uploaded_file = st.sidebar.file_uploader("Or Upload Custom Claim JSON", type=["json"])
if uploaded_file is not None:
    try:
        uploaded_json = json.load(uploaded_file)
        default_json_str = json.dumps(uploaded_json, indent=2)
        st.sidebar.success("Uploaded JSON loaded!")
    except Exception as e:
        st.sidebar.error(f"Invalid JSON file: {e}")

st.subheader("Claim Case Input JSON")
input_json_str = st.text_area("Edit or Review Claim JSON:", value=default_json_str, height=220)

analyze_btn = st.button("🚀 Analyze Claim Case", type="primary", use_container_width=True)

if analyze_btn:
    try:
        claim_data = json.loads(input_json_str)
    except Exception as e:
        st.error(f"Invalid JSON format: {e}")
        st.stop()

    with st.spinner("Executing 5-Agent LangGraph Analysis Workflow..."):
        result = run_claim_analysis(claim_data)

    st.markdown("---")
    st.subheader("📊 Analysis Decision & Audit Result")

    decision = result.get("decision", "NEEDS_REVIEW")
    confidence = result.get("confidence", 0.0)
    summary = result.get("summary", "")

    # Color coded badges
    badge_colors = {
        "ADMISSIBLE": ("#2e7d32", "🟢 ADMISSIBLE"),
        "ADMISSIBLE_WITH_LIMITS": ("#1565c0", "🔵 ADMISSIBLE WITH LIMITS"),
        "PARTIALLY_ADMISSIBLE": ("#f57f17", "🟡 PARTIALLY ADMISSIBLE"),
        "NOT_ADMISSIBLE": ("#c62828", "🔴 NOT ADMISSIBLE"),
        "NEEDS_REVIEW": ("#ef6c00", "🟠 NEEDS REVIEW (ABSTENTION)")
    }

    bg_color, label = badge_colors.get(decision, ("#424242", decision))

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(
            f"""
            <div style="background-color: {bg_color}; padding: 16px; border-radius: 8px; color: white; font-weight: bold; font-size: 22px; text-align: center;">
                {label}
            </div>
            """,
            unsafe_allow_html=True
        )
    with col2:
        st.metric("Confidence Score", f"{confidence * 100:.1f}%")
    with col3:
        st.metric("Case ID", result.get("case_id", "N/A"))

    st.info(f"**Decision Summary:** {summary}")

    # Tabs for detailed view
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🔍 Key Findings",
        "💰 Applicable Limits",
        "⚠️ Missing Evidence",
        "📜 Citations",
        "✅ Validation Audit",
        "⏱️ Execution Trace"
    ])

    with tab1:
        st.markdown("### Coverage & Policy Findings")
        findings = result.get("key_findings", [])
        if findings:
            for f in findings:
                refs = ", ".join(f.get("evidence_refs", [])) or "None"
                st.write(f"- **[{f.get('dimension').upper()}]** {f.get('finding')} *(Ref: `{refs}`)*")
        else:
            st.write("No specific restrictions or findings recorded.")

    with tab2:
        st.markdown("### Category Sub-Limits & Deductions")
        limits = result.get("applicable_limits", [])
        if limits:
            for lim in limits:
                st.warning(f"**{lim.get('category').replace('_', ' ').upper()}**: {lim.get('description')} (Cap: INR {lim.get('limit_amount_inr'):,.0f})")
        else:
            st.write("No specific category sub-limits triggered.")

    with tab3:
        st.markdown("### Evidence Gaps & Mandatory Abstention Reasons")
        missing = result.get("missing_evidence", [])
        if missing:
            for m in missing:
                st.error(f"❌ **Missing Evidence**: `{m}`")
        else:
            st.success("All required claim evidence and document criteria verified.")

    with tab4:
        st.markdown("### Policy PDF Citations & Excerpts")
        citations = result.get("citations", [])
        if citations:
            for idx, cit in enumerate(citations, 1):
                with st.expander(f"Citation #{idx}: Page {cit.get('page')} — {cit.get('section')} ({cit.get('chunk_id')})"):
                    st.write(f"**Source File:** `{cit.get('source')}`")
                    st.write(f"**Heading:** {cit.get('heading')}")
                    st.write(f"**Policy Text Snippet:**")
                    st.code(cit.get("text"), language="text")
        else:
            st.write("No direct policy citations attached.")

    with tab5:
        st.markdown("### Validation Agent Audit")
        val = result.get("validation", {})
        st.write(f"**Audit Status:** `{val.get('status', 'N/A')}`")
        if val.get("unsupported_claims"):
            st.error(f"Unsupported Claims: {val.get('unsupported_claims')}")
        if val.get("citation_errors"):
            st.error(f"Citation Errors: {val.get('citation_errors')}")
        if val.get("status") == "PASS":
            st.success("Validation Audit passed clean. All citations and policy rules verified.")

    with tab6:
        st.markdown("### Agent Execution Trace")
        trace = result.get("trace", [])
        for t in trace:
            st.text(t)

