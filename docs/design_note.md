# Aptino Health Claim Analyzer — Design Notes & Rationale

## Core Design Principles

### 1. Authoritative Policy Document
The supplied insurance policy PDF (`USGIC-CSCIndividualHealthInsurance_2017-2018.pdf`) is the sole authoritative source of insurance rules. The system does not invent policy rules from general knowledge or hardcode arbitrary rules without evidence linkage.

### 2. Mandatory Abstention (`NEEDS_REVIEW`)
When required evidence is missing (e.g. unverified hospital registration, missing hospital minimum criteria, unconfirmed medical necessity), the system strictly returns `NEEDS_REVIEW`. The system never guesses or forces a decision when evidence is insufficient.

### 3. Policy-Aware Chunking Strategy
Instead of splitting text blindly by character lengths, the ingestion engine tracks PDF page numbers (1-indexed), section titles (`SCOPE OF COVER`, `EXCLUSIONS`, `WAITING PERIODS`), and clause headings. This ensures retrieved chunks retain complete clause context and traceable page numbers.

### 4. Hybrid Retrieval Fusion (RRF) & Reranking
Single-method vector search can fail on exact keyword terms (such as "30 days" or "48 months" or specific procedure names). Combining dense vector search with sparse BM25 keyword retrieval using Reciprocal Rank Fusion ($k=60$) ensures high recall. The Cross-Encoder reranker then selects the top evidence chunks.

### 5. Multi-Agent Validation Loop
The 5th agent (Validation Agent) acts as an independent auditor. It verifies that every citation points to an actual retrieved chunk with matching page numbers and section titles. If validation fails, it triggers a controlled revision loop (up to 2 revisions max) or defaults to `NEEDS_REVIEW`.

