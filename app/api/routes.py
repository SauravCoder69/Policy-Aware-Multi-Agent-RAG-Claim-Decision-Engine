"""API Routes Module."""

import os
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from app.api.schemas import HealthResponse, AnalysisResponse
from app.graph.workflow import run_claim_analysis
from app.config import settings
from qdrant_client import QdrantClient

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    # Check Qdrant Cloud connectivity and collection existence
    qdrant_connected = False
    if settings.QDRANT_URL and settings.QDRANT_API_KEY:
        try:
            client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            qdrant_connected = settings.QDRANT_COLLECTION_NAME in collection_names
        except Exception:
            qdrant_connected = False
    
    # BM25 check remains based on local file existence
    bm25_exists = os.path.exists(settings.BM25_PATH)

    return HealthResponse(
        status="ok",
        vectorstore_indexed=qdrant_connected,
        bm25_indexed=bm25_exists
    )


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_claim(claim_data: Dict[str, Any]):
    if not claim_data:
        raise HTTPException(status_code=400, detail="Empty claim case payload.")

    try:
        result = run_claim_analysis(claim_data)
        return AnalysisResponse(**result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Claim analysis execution failed: {str(e)}")
