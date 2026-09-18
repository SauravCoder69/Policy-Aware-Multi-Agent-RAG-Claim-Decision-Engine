"""Executable script for policy PDF ingestion."""

import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.rag.ingestion import ingest_policy_pdf
from app.config import settings


def main():
    print("=== Starting Policy PDF Ingestion ===")
    pdf_path = settings.POLICY_PDF_PATH
    if not os.path.exists(pdf_path):
        print(f"Error: Policy PDF file does not exist at {pdf_path}")
        sys.exit(1)

    try:
        chunks = ingest_policy_pdf(pdf_path)
        print(f"=== Successfully Ingested {len(chunks)} Chunks ===")
    except Exception as e:
        print(f"Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
