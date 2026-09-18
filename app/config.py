"""Application Configuration Module."""

import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    # LLM Settings
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # Embedding & Retrieval Settings
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    QDRANT_PATH: str = os.getenv("QDRANT_PATH", str(BASE_DIR / "vectorstore" / "qdrant"))
    BM25_PATH: str = os.getenv("BM25_PATH", str(BASE_DIR / "vectorstore" / "bm25_index.pkl"))
    QDRANT_COLLECTION_NAME: str = os.getenv("QDRANT_COLLECTION_NAME", "policy_chunks")
    
    # Paths
    POLICY_PDF_PATH: str = os.getenv("POLICY_PDF_PATH", str(BASE_DIR / "data" / "policy" / "USGIC-CSCIndividualHealthInsurance_2017-2018.pdf"))
    PUBLIC_CASES_PATH: str = os.getenv("PUBLIC_CASES_PATH", str(BASE_DIR / "data" / "public_cases" / "public_test_cases.json"))
    CUSTOM_CASES_PATH: str = os.getenv("CUSTOM_CASES_PATH", str(BASE_DIR / "data" / "custom_cases" / "custom_test_cases.json"))
    
    # Retrieval parameters
    TOP_K: int = int(os.getenv("TOP_K", "10"))
    RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "5"))
    RRF_K: int = int(os.getenv("RRF_K", "60"))
    
    # Workflow limits
    REVISION_LIMIT: int = int(os.getenv("REVISION_LIMIT", "2"))


settings = Settings()
