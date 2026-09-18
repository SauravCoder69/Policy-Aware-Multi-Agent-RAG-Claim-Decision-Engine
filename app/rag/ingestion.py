"""Policy PDF Ingestion Engine.

Parses policy PDF page-by-page, extracts text with section/heading awareness,
chunks text logically, embeds vectors into Qdrant, and builds a BM25 index.
"""

import os
import re
import pickle
import pypdf
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rank_bm25 import BM25Okapi

from app.config import settings


def tokenize_text(text: str) -> List[str]:
    """Tokenize text for BM25 indexing."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in cleaned.split() if len(t) > 1]
    return tokens


def parse_and_chunk_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Parse PDF page-by-page and extract policy-aware chunks with metadata."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Policy PDF not found at path: {pdf_path}")

    reader = pypdf.PdfReader(pdf_path)
    filename = os.path.basename(pdf_path)
    chunks: List[Dict[str, Any]] = []

    current_section = "General Policy Rules"
    current_heading = "Policy Terms"

    # Known section header regex patterns
    section_patterns = [
        (r"(?i)SECTION\s*1\b.*", "Scope of Cover"),
        (r"(?i)SECTION\s*2\b.*", "Definitions"),
        (r"(?i)SECTION\s*3\b.*", "Exclusions"),
        (r"(?i)SECTION\s*4\b.*", "Conditions & Provisions"),
        (r"(?i)DEFINITIONS\b.*", "Definitions"),
        (r"(?i)EXCLUSIONS\b.*", "Exclusions"),
        (r"(?i)WAITING\s+PERIODS?\b.*", "Waiting Periods"),
        (r"(?i)SCOPE\s+OF\s+COVER\b.*", "Scope of Cover"),
        (r"(?i)SPECIAL\s+CONDITIONS\b.*", "Conditions & Provisions"),
    ]

    heading_patterns = [
        r"(?i)^\s*(?:\d+\.|\([a-z]\)|[A-Z\s]{4,})\s+([A-Za-z0-9\s\,\-\/]+)$",
        r"(?i)^\s*(Hospitalization Expenses|Room Rent|ICU|Domiciliary Hospitalization|Day Care|Waiting Period|Pre-existing|Exclusions|Cumulative Bonus|Portability|Pre-hospitalization|Post-hospitalization)\b.*"
    ]

    for page_idx, page in enumerate(reader.pages):
        page_num = page_idx + 1
        raw_text = page.extract_text() or ""
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        if not lines:
            continue

        # Page text blocks grouping
        page_text_blocks = []
        current_block = []

        for line in lines:
            # Check section updates
            for pat, sec_name in section_patterns:
                if re.search(pat, line):
                    current_section = sec_name
                    break

            # Check heading updates
            for h_pat in heading_patterns:
                match = re.search(h_pat, line)
                if match:
                    potential_h = line[:60].strip()
                    if len(potential_h) > 3:
                        current_heading = potential_h
                    break

            current_block.append(line)
            # Break into blocks of 5-8 lines
            if len(current_block) >= 6:
                block_str = " ".join(current_block)
                if len(block_str) > 100:
                    page_text_blocks.append((current_section, current_heading, block_str))
                    current_block = []

        if current_block:
            block_str = " ".join(current_block)
            if len(block_str) > 50:
                page_text_blocks.append((current_section, current_heading, block_str))

        # Create chunks with 1-indexed chunk_id per page
        for c_idx, (sec, head, text_content) in enumerate(page_text_blocks):
            chunk_id = f"policy_p{page_num:02d}_c{c_idx+1:02d}"
            chunks.append({
                "chunk_id": chunk_id,
                "source": filename,
                "page": page_num,
                "section": sec,
                "heading": head,
                "text": text_content
            })

    return chunks


def ingest_policy_pdf(pdf_path: str = None) -> List[Dict[str, Any]]:
    """Ingest policy PDF, populate Qdrant collection and BM25 index."""
    if pdf_path is None:
        pdf_path = settings.POLICY_PDF_PATH

    print(f"Reading policy PDF from: {pdf_path}")
    chunks = parse_and_chunk_pdf(pdf_path)
    print(f"Extracted {len(chunks)} policy chunks.")

    if not chunks:
        raise ValueError("No text chunks extracted from policy PDF.")

    # 1. Dense Embeddings & Qdrant Store
    print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    vector_size = embeddings.shape[1]

    # Create Qdrant cloud client with timeout
    if not settings.QDRANT_URL or not settings.QDRANT_API_KEY:
        raise ValueError("QDRANT_URL and QDRANT_API_KEY must be set in environment variables for Qdrant Cloud connection")
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60)

    # Re-create collection
    collection_name = settings.QDRANT_COLLECTION_NAME
    collections = [c.name for c in client.get_collections().collections]
    if collection_name in collections:
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )

    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        points.append(PointStruct(
            id=idx + 1,
            vector=emb.tolist(),
            payload=chunk
        ))

    # Upload in batches to avoid timeout
    batch_size = 50
    total_batches = (len(points) + batch_size - 1) // batch_size
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(points))
        batch = points[start_idx:end_idx]
        client.upsert(collection_name=collection_name, points=batch)
        print(f"Uploading batch {batch_idx + 1}/{total_batches} ({len(batch)} points)")

    print(f"Stored {len(points)} vectors in Qdrant collection '{collection_name}'.")

    # 2. BM25 Index Creation
    tokenized_corpus = [tokenize_text(t) for t in texts]
    bm25 = BM25Okapi(tokenized_corpus)

    bm25_data = {
        "bm25": bm25,
        "chunks": chunks
    }

    bm25_file = settings.BM25_PATH
    os.makedirs(os.path.dirname(bm25_file), exist_ok=True)
    with open(bm25_file, "wb") as f:
        pickle.dump(bm25_data, f)

    print(f"Saved BM25 index and chunk metadata to '{bm25_file}'.")
    return chunks
