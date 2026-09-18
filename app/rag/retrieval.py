"""Hybrid Retrieval Module.

Combines Dense Vector Search (Qdrant) and Sparse Lexical Search (BM25)
using Reciprocal Rank Fusion (RRF).
"""

import os
import pickle
import re
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

from app.config import settings


def tokenize_text(text: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in cleaned.split() if len(t) > 1]


class HybridRetriever:
    def __init__(self):
        self.embedding_model = None
        self.qdrant_client = None
        self.bm25_data = None

    def _lazy_init(self):
        if self.embedding_model is None:
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

        if self.qdrant_client is None:
            if settings.QDRANT_URL and settings.QDRANT_API_KEY:
                self.qdrant_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            else:
                raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables for Qdrant Cloud connection")

        if self.bm25_data is None and os.path.exists(settings.BM25_PATH):
            with open(settings.BM25_PATH, "rb") as f:
                self.bm25_data = pickle.load(f)

    def dense_search(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        self._lazy_init()
        query_vector = self.embedding_model.encode(query, convert_to_numpy=True).tolist()
        
        try:
            results = self.qdrant_client.query_points(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                query=query_vector,
                limit=top_k
            )
            hits = []
            for hit in results.points:
                payload = dict(hit.payload)
                payload["dense_score"] = float(hit.score)
                hits.append(payload)
            return hits
        except Exception as e:
            print(f"Dense search warning: {e}")
            return []

    def sparse_search(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        self._lazy_init()
        if not self.bm25_data:
            return []

        bm25 = self.bm25_data["bm25"]
        chunks = self.bm25_data["chunks"]

        tokenized_query = tokenize_text(query)
        if not tokenized_query:
            return []

        scores = bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        hits = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = dict(chunks[idx])
                chunk["bm25_score"] = float(scores[idx])
                hits.append(chunk)
        return hits

    def hybrid_search(self, query: str, top_k: int = None) -> List[Dict[str, Any]]:
        if top_k is None:
            top_k = settings.TOP_K

        dense_hits = self.dense_search(query, top_k=top_k * 2)
        sparse_hits = self.sparse_search(query, top_k=top_k * 2)

        # Reciprocal Rank Fusion (RRF)
        rrf_k = settings.RRF_K
        chunk_scores: Dict[str, float] = {}
        chunk_data: Dict[str, Dict[str, Any]] = {}

        # Process dense ranks
        for rank, hit in enumerate(dense_hits, start=1):
            cid = hit["chunk_id"]
            rrf_score = 1.0 / (rrf_k + rank)
            chunk_scores[cid] = chunk_scores.get(cid, 0.0) + rrf_score
            chunk_data[cid] = hit

        # Process sparse ranks
        for rank, hit in enumerate(sparse_hits, start=1):
            cid = hit["chunk_id"]
            rrf_score = 1.0 / (rrf_k + rank)
            chunk_scores[cid] = chunk_scores.get(cid, 0.0) + rrf_score
            if cid not in chunk_data:
                chunk_data[cid] = hit
            else:
                chunk_data[cid]["bm25_score"] = hit.get("bm25_score", 0.0)

        # Sort by RRF score
        sorted_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)[:top_k]

        final_candidates = []
        for rank, cid in enumerate(sorted_ids, start=1):
            item = dict(chunk_data[cid])
            item["rrf_rank"] = rank
            item["fusion_score"] = round(chunk_scores[cid], 5)
            item.setdefault("dense_score", 0.0)
            item.setdefault("bm25_score", 0.0)
            final_candidates.append(item)

        return final_candidates


_retriever = HybridRetriever()


def hybrid_search(query: str, top_k: int = None) -> List[Dict[str, Any]]:
    return _retriever.hybrid_search(query, top_k=top_k)
