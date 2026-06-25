"""Thin entrypoint kept for docker-compose / back-compat.

Real logic lives in src/rag/ingest.py (content-type-guarded, fail-loud).
"""

from src.rag.ingest import ingest

if __name__ == "__main__":
    ingest()
    print("\nData ingestion and vectorization complete.")
