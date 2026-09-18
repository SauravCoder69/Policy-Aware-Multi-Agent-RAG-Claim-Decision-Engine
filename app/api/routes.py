"""API Routes Module."""

import os
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from app.api.schemas import HealthResponse, AnalysisResponse
from app.graph.workflow import run_claim_analysis
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    qdrant_exists = os.path.exists(settings.QDRANT_PATH)
    bm25_exists = os.path.exists(settings.BM25_PATH)

    return HealthResponse(
        status="ok",
        vectorstore_indexed=qdrant_exists,
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
