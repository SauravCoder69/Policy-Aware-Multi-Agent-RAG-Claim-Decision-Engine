"""FastAPI Main Entrypoint Application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(
    title="Aptino AI Engineer Take-Home — Health Insurance Claim Analyzer",
    description="Evidence-backed health insurance claim decisioning system using RAG and LangGraph multi-agent workflow.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.1", port=8000, reload=True)
