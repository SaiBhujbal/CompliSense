"""
Citation-grounded retrieval for the RBI corpus.

Pipeline (all stages env-toggleable in config):
    dense (bge-large) ──┐
                        ├─ reciprocal-rank fusion ─→ cross-encoder rerank ─→ score threshold ─→ top-K
    BM25 (keyword) ─────┘

Every returned chunk keeps its ``source``/``page`` metadata so the answerer can
cite real documents instead of inventing them. If nothing clears the threshold,
we return an empty list — the caller MUST refuse rather than hallucinate.

Import / model / Chroma failures never propagate as uncaught exceptions from
``retrieve()`` — they raise ``RagUnavailable`` so the RBI agent can refuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document

from .. import _bootstrap  # noqa: F401  -- init torch/ST before chromadb/onnxruntime
from .. import config
from .embeddings import RagUnavailable, embeddings_ready, get_embeddings


@dataclass
class RetrievedChunk:
    document: Document
    score: float

    @property
    def source(self) -> str:
        return self.document.metadata.get("source", "unknown")

    @property
    def page(self):
        return self.document.metadata.get("page", "?")


def _ensure_store_exists() -> None:
    root = Path(config.CHROMA_DB_PATH)
    if not root.exists() or not (root / "chroma.sqlite3").exists():
        raise RagUnavailable(
            f"Vector store not found at {config.CHROMA_DB_PATH}. "
            "Run `docker compose --profile ingest run --rm ingest` "
            "(or `python ingest_data.py`) first."
        )


@lru_cache(maxsize=1)
def get_vector_store():
    _ensure_store_exists()
    try:
        from langchain_chroma import Chroma

        return Chroma(
            persist_directory=config.CHROMA_DB_PATH,
            embedding_function=get_embeddings(),
            collection_name=config.CHROMA_COLLECTION,
        )
    except RagUnavailable:
        raise
    except Exception as e:  # noqa: BLE001
        raise RagUnavailable(
            f"Could not open Chroma store: {type(e).__name__}: {e}"
        ) from e


@lru_cache(maxsize=1)
def _all_documents() -> list[Document]:
    """Materialize the whole corpus for BM25 (RBI corpus is small enough)."""
    store = get_vector_store()
    raw = store.get(include=["documents", "metadatas"])
    return [
        Document(page_content=text, metadata=meta or {})
        for text, meta in zip(raw.get("documents", []), raw.get("metadatas", []))
    ]


@lru_cache(maxsize=1)
def _bm25():
    from rank_bm25 import BM25Okapi

    docs = _all_documents()
    corpus = [d.page_content.lower().split() for d in docs]
    return BM25Okapi(corpus), docs


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(config.RERANKER_MODEL, device=config.EMBEDDING_DEVICE)


def _dense_candidates(query: str) -> list[tuple[Document, float]]:
    store = get_vector_store()
    return store.similarity_search_with_relevance_scores(
        query, k=config.RETRIEVAL_CANDIDATE_K
    )


def _bm25_candidates(query: str) -> list[Document]:
    bm25, docs = _bm25()
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [d for d, _ in ranked[: config.RETRIEVAL_CANDIDATE_K]]


def _doc_key(doc: Document) -> tuple:
    import hashlib

    digest = hashlib.md5(doc.page_content.encode("utf-8")).hexdigest()
    return (doc.metadata.get("source"), doc.metadata.get("page"), digest)


def _fuse(dense: list[Document], sparse: list[Document], k: int = 60) -> list[Document]:
    scores: dict[tuple, float] = {}
    keep: dict[tuple, Document] = {}
    for ranked in (dense, sparse):
        for rank, doc in enumerate(ranked):
            key = _doc_key(doc)
            keep[key] = doc
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [keep[key] for key, _ in ordered]


def _sigmoid(x: float) -> float:
    import math

    return 1.0 / (1.0 + math.exp(-x))


def retrieve(query: str) -> list[RetrievedChunk]:
    """Return the top-K grounded chunks above threshold (possibly empty).

    Raises ``RagUnavailable`` when embeddings/Chroma cannot load — never an
    opaque ImportError. Callers (RBI agent) must catch and refuse honestly.
    """
    ok, reason = embeddings_ready()
    if not ok:
        raise RagUnavailable(reason)

    try:
        dense_scored = _dense_candidates(query)
    except RagUnavailable:
        raise
    except Exception as e:  # noqa: BLE001
        raise RagUnavailable(
            f"Dense retrieval failed: {type(e).__name__}: {e}"
        ) from e

    dense_docs = [d for d, _ in dense_scored]

    if config.HYBRID_ENABLED:
        try:
            candidates = _fuse(dense_docs, _bm25_candidates(query))
        except Exception:  # noqa: BLE001 — BM25 is optional enrichment
            candidates = dense_docs
    else:
        candidates = dense_docs

    if not candidates:
        return []

    if config.RERANK_ENABLED:
        try:
            ce = _reranker()
            pairs = [(query, d.page_content) for d in candidates]
            raw_scores = ce.predict(pairs)
            scored = [
                RetrievedChunk(doc, _sigmoid(float(s)))
                for doc, s in zip(candidates, raw_scores)
            ]
        except Exception:  # noqa: BLE001 — fall back to dense scores
            dense_map = {_doc_key(d): s for d, s in dense_scored}
            scored = [
                RetrievedChunk(doc, float(dense_map.get(_doc_key(doc), 0.0)))
                for doc in candidates
            ]
    else:
        dense_map = {_doc_key(d): s for d, s in dense_scored}
        scored = [
            RetrievedChunk(doc, float(dense_map.get(_doc_key(doc), 0.0)))
            for doc in candidates
        ]

    scored.sort(key=lambda c: c.score, reverse=True)
    grounded = [c for c in scored if c.score >= config.RETRIEVAL_SCORE_THRESHOLD]
    return grounded[: config.RETRIEVAL_TOP_K]
