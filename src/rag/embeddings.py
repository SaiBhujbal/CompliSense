"""Shared, cached embedding function so the model loads once per process.

Never raises bare ImportError into the agent graph — callers get RagUnavailable
with a clear, user-facing reason (install missing, model download failed, etc.).
"""

from __future__ import annotations

from functools import lru_cache

from .. import _bootstrap  # noqa: F401  -- init torch/ST before chromadb


class RagUnavailable(RuntimeError):
    """Retrieval/embeddings cannot run; RBI path should refuse honestly."""


def embeddings_ready() -> tuple[bool, str]:
    """Return (ok, reason). Safe to call from health checks / agents."""
    try:
        import sentence_transformers  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return False, (
            "sentence-transformers is not importable "
            f"({type(e).__name__}: {e}). "
            "Install with: pip install sentence-transformers torch"
        )
    try:
        import torch  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return False, f"torch is not importable ({type(e).__name__}: {e})"
    return True, "ok"


@lru_cache(maxsize=1)
def get_embeddings():
    """Return the configured embedding model (loaded once, then cached)."""
    ok, reason = embeddings_ready()
    if not ok:
        raise RagUnavailable(reason)
    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        from .. import config

        return HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs={"device": config.EMBEDDING_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )
    except Exception as e:  # noqa: BLE001
        raise RagUnavailable(
            f"Could not load embedding model: {type(e).__name__}: {e}"
        ) from e
