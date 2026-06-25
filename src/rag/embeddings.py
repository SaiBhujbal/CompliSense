"""Shared, cached embedding function so the model loads once per process."""

from .. import _bootstrap  # noqa: F401  -- init torch/ST before chromadb

from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from .. import config


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Return the configured embedding model (loaded once, then cached)."""
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": config.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
