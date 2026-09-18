"""Policy Evidence Agent.

Executes targeted queries from the investigation plan using hybrid retrieval and reranking,
producing cited evidence from the policy PDF.
"""

from typing import Dict, Any, List
from app.graph.state import ClaimState
from app.rag.retrieval import hybrid_search
from app.rag.reranker import rerank_chunks


def run_policy_evidence_agent(state: ClaimState) -> ClaimState:
    investigation_plan = state.get("investigation_plan", [])
    seen_chunk_ids = set()
    retrieved_evidence: List[Dict[str, Any]] = []

    for item in investigation_plan:
        query = item.get("query", "")
        dimension = item.get("dimension", "general")

        # Hybrid Search
        candidates = hybrid_search(query, top_k=6)
        # Rerank
        top_chunks = rerank_chunks(query, candidates, top_n=3)

        for chunk in top_chunks:
            cid = chunk["chunk_id"]
            if cid not in seen_chunk_ids:
                seen_chunk_ids.add(cid)
                chunk_record = dict(chunk)
                chunk_record["dimension"] = dimension
                retrieved_evidence.append(chunk_record)

    state["retrieved_evidence"] = retrieved_evidence

    trace_msg = f"[PolicyEvidenceAgent] Executed {len(investigation_plan)} queries. Retrieved and reranked {len(retrieved_evidence)} unique policy evidence chunks."
    trace = state.get("trace", [])
    trace.append(trace_msg)
    state["trace"] = trace

    return state
