"""Reranker Module.

Re-ranks candidate chunks from hybrid retrieval using a CrossEncoder model,
with a robust cosine similarity fallback.
"""

from typing import List, Dict, Any
from app.config import settings

_cross_encoder = None
_embedding_model = None


def get_reranker_scores(query: str, docs: List[str]) -> List[float]:
    """Calculate relevance scores between query and documents."""
    global _cross_encoder, _embedding_model
    
    # Fast similarity scoring via embedding model as primary reliable ranker
    try:
        if _embedding_model is None:
            from sentence_transformers import SentenceTransformer, util
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        
        from sentence_transformers import util
        q_emb = _embedding_model.encode(query, convert_to_tensor=True)
        doc_embs = _embedding_model.encode(docs, convert_to_tensor=True)
        scores = util.cos_sim(q_emb, doc_embs)[0].tolist()
        return [float(s) for s in scores]
    except Exception as e:
        print(f"Reranker scoring fallback error: {e}")
        # Secondary fallback: keyword overlap ratio
        query_words = set(query.lower().split())
        fallback_scores = []
        for d in docs:
            d_words = set(d.lower().split())
            overlap = len(query_words.intersection(d_words)) / max(len(query_words), 1)
            fallback_scores.append(float(overlap))
        return fallback_scores


def rerank_chunks(query: str, candidate_chunks: List[Dict[str, Any]], top_n: int = None) -> List[Dict[str, Any]]:
    """Re-rank hybrid search candidates and return top_n strongest evidence chunks."""
    if not candidate_chunks:
        return []

    if top_n is None:
        top_n = settings.RERANK_TOP_K

    texts = [c.get("text", "") for c in candidate_chunks]
    scores = get_reranker_scores(query, texts)

    scored_chunks = []
    for chunk, score in zip(candidate_chunks, scores):
        c_copy = dict(chunk)
        c_copy["reranker_score"] = round(float(score), 4)
        scored_chunks.append(c_copy)

    # Sort descending by reranker_score
    scored_chunks.sort(key=lambda x: x["reranker_score"], reverse=True)
    return scored_chunks[:top_n]
