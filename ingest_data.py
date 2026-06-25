"""Thin entrypoint kept for docker-compose / back-compat.

Real logic lives in src/rag/ingest.py (content-type-guarded, fail-loud).
"""

# Initialize torch + sentence-transformers native libs BEFORE chromadb/onnxruntime
# (imported via langchain_chroma) to avoid an OpenMP/native segfault on this CPU.
import os  # noqa: E402

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import torch  # noqa: E402

torch.set_num_threads(1)
import sentence_transformers  # noqa: E402,F401

from src.rag.ingest import ingest  # noqa: E402

if __name__ == "__main__":
    ingest()
    print("\nData ingestion and vectorization complete.")
