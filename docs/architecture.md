# Aptino Health Claim Analyzer — System Architecture

## Overview

The Aptino Health Claim Analyzer is a modular, evidence-backed decision system for evaluating synthetic health insurance claim JSONs against an authoritative insurance policy PDF (`USGIC-CSCIndividualHealthInsurance_2017-2018.pdf`).

The system uses **RAG (Retrieval-Augmented Generation)** with **Hybrid Retrieval** (Dense Qdrant Vectors + Sparse BM25 Keywords) combined with **Reciprocal Rank Fusion (RRF)** and **Cross-Encoder Reranking**, orchestrated via a **5-Agent LangGraph Workflow**.

---

## System Workflow Diagram

```text
Claim JSON Input
       │
       ▼
Case Analysis Agent (Extract Facts & Investigation Plan)
       │
       ▼
Policy Evidence Agent (Multi-query Hybrid RAG Retrieval)
       │  ├── Qdrant Dense Vector Search (Sentence Transformers)
       │  ├── BM25 Sparse Lexical Search (rank_bm25)
       │  ├── Reciprocal Rank Fusion (RRF k=60)
       │  └── Cross-Encoder Reranking
       │
       ▼
Coverage & Exclusion Agent (Fact vs Policy Evidence Matching)
       │
       ▼
Decision Agent (ADMISSIBLE / LIMITS / PARTIAL / NOT_ADMISSIBLE / NEEDS_REVIEW)
       │
       ▼
Validation Agent (Audit Citations, Page/Section Validity, Unsupported Claims)
       │
       ├── [FAIL & Revisions < 2] ──► Loop Back to Decision Agent
       │
       ▼
  [PASS / Final]
       │
       ▼
Structured Response (FastAPI / Streamlit UI)
```

---

## Component Architecture

### 1. Policy Ingestion Pipeline (`app/rag/ingestion.py`)
- Reads the PDF page-by-page using `pypdf`, preserving page numbers.
- Detects section boundaries (`SCOPE OF COVER`, `DEFINITIONS`, `EXCLUSIONS`, `WAITING PERIODS`, `CONDITIONS`) and heading titles.
- Creates policy-aware chunks with metadata: `chunk_id`, `source`, `page`, `section`, `heading`, `text`.
- Generates 384-dimensional dense embeddings using `sentence-transformers/all-MiniLM-L6-v2`.
- Stores dense vectors in Qdrant Cloud collection (`policy_chunks`) using `QDRANT_URL` and `QDRANT_API_KEY`.
- Tokenizes text and builds a local `BM25Okapi` index saved to `vectorstore/bm25_index.pkl`.

### 2. Hybrid Retrieval & Reranker (`app/rag/retrieval.py`, `app/rag/reranker.py`)
- **Dense Search**: Cosine similarity query on Qdrant Cloud using `query_points()` API (qdrant-client 1.19.0).
- **Sparse Search**: Keyword frequency ranking via BM25.
- **Reciprocal Rank Fusion (RRF)**: Merges candidates using:
  $$RRF(d) = \sum_{m \in \{dense, bm25\}} \frac{1}{60 + rank_m(d)}$$
- **Reranker**: Cross-Encoder cosine similarity pass returning top-N evidence chunks preserving citations and reranker scores.

### 3. The Five Specialized Agents (`app/agents/`)
1. **Case Analysis Agent**: Fact extraction, missing evidence detection, multi-query investigation planning.
2. **Policy Evidence Agent**: Executes multi-query hybrid retrieval against policy RAG index.
3. **Coverage & Exclusion Agent**: Evaluates coverage, initial 30-day waiting periods, 48-month PED rules, exclusions (cosmetic/experimental), sub-limits (domiciliary 20%, cataract cap, room rent cap), pre/post hospitalization windows, and hospital definition criteria.
4. **Decision Agent**: Derives final status (`ADMISSIBLE`, `ADMISSIBLE_WITH_LIMITS`, `PARTIALLY_ADMISSIBLE`, `NOT_ADMISSIBLE`, `NEEDS_REVIEW`). Mandates `NEEDS_REVIEW` if hospital registration or medical necessity is unverified.
5. **Validation Agent**: Audits citations, verifies page/section numbers, prevents hallucinated claims, and controls revision loops.

### 4. API & Frontend Interfaces (`app/main.py`, `frontend/app.py`)
- **FastAPI**: Exposes `GET /health` and `POST /analyze`.
- **Streamlit**: Interactive reviewer dashboard with color-coded status badges, findings, limits, citations, and agent execution trace.

