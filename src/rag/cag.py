"""
Cache-Augmented Generation (CAG) corpus preload for the RBI agent.

When the RBI corpus fits the model window, we preload the whole thing (with
source tags) and let the model answer without a retrieval step. The provider's
prompt cache (GLM-5.2 cached input ~$0.26/1M) makes the repeated prefix cheap.
If the corpus exceeds the safety ceiling, callers fall back to retrieval.

Failures raise RagUnavailable (or return False) — never an uncaught ImportError.
"""

from functools import lru_cache

from .. import config
from .embeddings import RagUnavailable


@lru_cache(maxsize=1)
def corpus_fits_window() -> bool:
    """Heuristic token estimate (chars/4) vs the CAG ceiling."""
    try:
        from .retriever import _all_documents

        docs = _all_documents()
    except Exception:  # noqa: BLE001
        return False
    approx_tokens = sum(len(d.page_content) for d in docs) // 3
    return approx_tokens <= config.CAG_MAX_CORPUS_TOKENS


@lru_cache(maxsize=1)
def preloaded_corpus() -> tuple[str, tuple]:
    """Return (corpus_text_with_[S#]_tags, sources_tuple) for the whole corpus."""
    try:
        from .retriever import _all_documents

        docs = _all_documents()
    except RagUnavailable:
        raise
    except Exception as e:  # noqa: BLE001
        raise RagUnavailable(f"CAG preload failed: {type(e).__name__}: {e}") from e

    blocks, sources = [], []
    for i, d in enumerate(docs, start=1):
        sid = f"S{i}"
        src = d.metadata.get("source", "unknown")
        page = d.metadata.get("page", "?")
        sources.append({"id": sid, "title": src, "ref": f"{src} p.{page}"})
        blocks.append(f"[{sid}] ({src} p.{page})\n{d.page_content}")
    return "\n\n".join(blocks), tuple(tuple(s.items()) for s in sources)
