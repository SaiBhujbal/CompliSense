"""Cue-recovery at scale: keyword overlap vs embedding retrieval (local, no API).

The DEEP ("back-of-mind") RMC mode keeps ~11% of tokens resident and recovers
verbatim spans from the dormant tier on cue. On n=11 facts with ~40 chunks the
keyword recovery scored 100% — but at scale (thousands of dormant spans) keyword
overlap should degrade. This experiment measures that honestly and tests the
production fix: bge-small embedding retrieval over dormant spans.

Metric: fact-recovery@k — does the top-k recovered dormant spans contain the
grounded fact's verbatim surface? Plus tokens pulled per query at k.

Run:  python -m evals.experiments.recovery_scale
"""

import src._bootstrap  # noqa: F401  -- torch before chromadb; encode once

import json
import random
import sys
from pathlib import Path

import numpy as np

from evals.schema import BenchItem  # noqa: F401  (dataset shape reference)
from src.memory.dtcam import _keywords
from src.rag.compression import _approx_tokens, _split

_HERE = Path(__file__).parent.parent
_GROUND = _HERE / "dataset" / "normbench_grounding.json"
_BENCH = _HERE / "dataset" / "rbi_normbench.jsonl"


def main() -> int:
    from sentence_transformers import SentenceTransformer

    from src.rag.retriever import _all_documents

    docs = _all_documents()
    grounding = json.loads(_GROUND.read_text(encoding="utf-8"))
    questions = {json.loads(l)["id"]: json.loads(l)["question"]
                 for l in _BENCH.read_text(encoding="utf-8").splitlines() if l.strip()}

    # facts: (surface, question)
    facts, pages = [], set()
    for item_id, obs in grounding.items():
        if not isinstance(obs, dict) or "status" in obs:
            continue
        for r in obs.values():
            if r.get("status") == "grounded":
                pages.add((r["source"], r["page"]))
                facts += [(s, questions[item_id]) for s in r["matched"].values()]

    # Span pool at SCALE: all sentences from grounded pages + 400 random chunks.
    rng = random.Random(11)
    sel = [d for d in docs if (d.metadata.get("source"), d.metadata.get("page")) in pages]
    others = [d for d in docs if d not in sel]
    sel += rng.sample(others, min(400, len(others)))
    spans = []
    for d in sel:
        spans += [s for s in _split(d.page_content) if len(s) > 20]
    print(f"Dormant span pool: {len(spans)} spans from {len(sel)} chunks "
          f"(~{sum(_approx_tokens(s) for s in spans)} tokens dormant)")

    qs = sorted({q for _, q in facts})
    q_idx = {q: i for i, q in enumerate(qs)}

    # ---- keyword recovery: rank by |cue_kw ∩ span_kw| ---------------------- #
    span_kws = [_keywords(s) for s in spans]

    def kw_topk(q: str, k: int) -> list[int]:
        ck = _keywords(q)
        scored = sorted(range(len(spans)), key=lambda i: -len(ck & span_kws[i]))
        return scored[:k]

    # ---- embedding recovery: bge-small cosine ------------------------------ #
    model = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    emb_s = model.encode(spans, normalize_embeddings=True, batch_size=64,
                         show_progress_bar=False)
    emb_q = model.encode(qs, normalize_embeddings=True, show_progress_bar=False)
    sims = emb_q @ emb_s.T  # (Q, S)

    def emb_topk(q: str, k: int) -> list[int]:
        return list(np.argsort(-sims[q_idx[q]])[:k])

    # ---- score ------------------------------------------------------------- #
    print(f"\n{'k':>4} | {'keyword R@k':>12} | {'embed R@k':>10} | "
          f"{'kw tok/q':>9} | {'emb tok/q':>9}")
    for k in (5, 10, 20, 40):
        hit_kw = hit_emb = tok_kw = tok_emb = 0
        for q in qs:
            ids_kw, ids_emb = kw_topk(q, k), emb_topk(q, k)
            tok_kw += sum(_approx_tokens(spans[i]) for i in ids_kw)
            tok_emb += sum(_approx_tokens(spans[i]) for i in ids_emb)
            for surf, fq in facts:
                if fq != q:
                    continue
                if any(surf.lower() in spans[i].lower() for i in ids_kw):
                    hit_kw += 1
                if any(surf.lower() in spans[i].lower() for i in ids_emb):
                    hit_emb += 1
        n = len(facts)
        print(f"{k:>4} | {hit_kw/n:>11.0%} | {hit_emb/n:>9.0%} | "
              f"{tok_kw//len(qs):>9} | {tok_emb//len(qs):>9}")

    # ---- trace-level recovery: retrieve CHUNKS, resurface their spans ------ #
    # Span-level recovery degrades at scale; the earlier memory_rag_compare run
    # showed chunk-level dense retrieval stays 100%. Test recovery at TRACE
    # granularity: embed whole chunks, top-k chunks -> all their spans recover.
    chunk_texts = [d.page_content for d in sel]
    chunk_spans = [[s for s in _split(t) if len(s) > 20] for t in chunk_texts]
    emb_c = model.encode(chunk_texts, normalize_embeddings=True, batch_size=32,
                         show_progress_bar=False)
    sims_c = emb_q @ emb_c.T

    print(f"\nTRACE-level recovery (top-k chunks, all their dormant spans return):")
    print(f"{'k':>4} | {'trace R@k':>10} | {'tok/q':>7}")
    for k in (1, 3, 5, 10):
        hit = tok = 0
        for q in qs:
            ids = list(np.argsort(-sims_c[q_idx[q]])[:k])
            recovered = " ".join(" ".join(chunk_spans[i]) for i in ids).lower()
            tok += sum(_approx_tokens(s) for i in ids for s in chunk_spans[i])
            for surf, fq in facts:
                if fq == q and surf.lower() in recovered:
                    hit += 1
        print(f"{k:>4} | {hit/len(facts):>9.0%} | {tok//len(qs):>7}")

    print(f"\nn={len(facts)} facts, {len(qs)} cues. Honest notes: surfaces are "
          "verbatim-match; single encoder (bge-small, CPU); pool is corpus-real "
          "but the questions were written for these facts (no hard negatives "
          "with near-identical wording yet).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
