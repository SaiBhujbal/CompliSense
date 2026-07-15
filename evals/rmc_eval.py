"""RMC mechanism eval — zero API cost, REAL corpus + REAL amendments.

Tests the four RMC claims (research/REGULATORY_MEMORY_CONSOLIDATION.md) at the
mechanism level, against the grounded NormBench facts from evals/normbench_ground.py:

  VSI  verbatim normative recall through consolidation
       (vs a normativity-blind head-truncation summarizer)
  CGW  citation-gated write-back rejects a deliberately drifted trace
  AAI  after the 6 real simulated amendments, RMC serves the AMENDED law;
       a recency-based memory (prior-art default) stays stale
  $    standing-token reduction of consolidation

Honest scope: deterministic mechanism demo (no LLM). Step 3 measures LLM-quality
consolidation on Groq with pre-registered hypotheses.

Run:  python -m evals.rmc_eval
"""

import src._bootstrap  # noqa: F401  -- torch before chromadb

import json
import random
import re
import sys
from pathlib import Path

from src.memory.rmc import RMCMemory, RecencyMemory
from src.rag.compression import _approx_tokens, _split

_HERE = Path(__file__).parent
_GROUND = _HERE / "dataset" / "normbench_grounding.json"
_AMEND = _HERE / "dataset" / "normbench_amendments.jsonl"
_BENCH = _HERE / "dataset" / "rbi_normbench.jsonl"


class LossyHeadMemory:
    """Generic summarizer baseline: keeps the FIRST 30% of sentences of each
    chunk — position-based, normativity-blind (what a naive consolidation does)."""

    def __init__(self) -> None:
        self.gists: list[str] = []

    def ingest_and_meditate(self, chunks) -> None:
        for text, _, _ in chunks:
            sents = _split(text)
            keep = max(1, int(len(sents) * 0.30))
            self.gists.append(" ".join(sents[:keep]))

    def context(self, cue: str = "") -> str:
        return " ".join(self.gists)

    def standing_tokens(self) -> int:
        return sum(_approx_tokens(g) for g in self.gists)


def _ci_replace(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), new, text, flags=re.IGNORECASE)


def main() -> int:
    from src.rag.retriever import _all_documents

    docs = _all_documents()
    grounding = json.loads(_GROUND.read_text(encoding="utf-8"))
    amendments = [json.loads(l) for l in _AMEND.read_text(encoding="utf-8").splitlines() if l.strip()]

    # source_lookup[(source, page)] = concatenated chunk text of that page
    lookup: dict = {}
    for d in docs:
        key = (d.metadata.get("source", "?"), d.metadata.get("page", "?"))
        lookup[key] = (lookup.get(key, "") + "\n" + d.page_content).strip()

    # Grounded facts: (surface, source, page, question-cue) from the grounding report.
    questions = {json.loads(l)["id"]: json.loads(l)["question"]
                 for l in _BENCH.read_text(encoding="utf-8").splitlines() if l.strip()}
    facts = []
    pages = set()
    for item_id, obs in grounding.items():
        if not isinstance(obs, dict) or "status" in obs:
            continue
        for r in obs.values():
            if r.get("status") == "grounded":
                pages.add((r["source"], r["page"]))
                facts += [(surf, r["source"], r["page"], questions.get(item_id, ""))
                          for surf in r["matched"].values()]
    print(f"Grounded facts: {len(facts)} across {len(pages)} source pages; "
          f"amendments: {len(amendments)}")

    # Chunk set: all grounded pages + 30 seeded distractor chunks.
    rng = random.Random(7)
    chunks = [(lookup[p], p[0], p[1]) for p in sorted(pages, key=str)]
    others = [d for d in docs
              if (d.metadata.get("source"), d.metadata.get("page")) not in pages]
    for d in rng.sample(others, min(30, len(others))):
        chunks.append((d.page_content, d.metadata.get("source", "?"), d.metadata.get("page", "?")))
    raw_tokens = sum(_approx_tokens(t) for t, _, _ in chunks)

    # ----- systems ----------------------------------------------------- #
    rmc, rec, lossy = RMCMemory(), RecencyMemory(), LossyHeadMemory()
    deep = RMCMemory(deep=True)
    rep = None
    for mem in (rmc, rec):
        mem.ingest(list(chunks))
        rep = mem.meditate(lookup)
    deep.ingest(list(chunks))
    deep.meditate(lookup)
    lossy.ingest_and_meditate(chunks)

    # ----- VSI: verbatim normative recall after consolidation ----------- #
    # Three honest tiers: active gist only; active + question-cued dormant
    # recovery (the intended read path); recoverable (nothing deleted?).
    def vnr_active(mem) -> float:
        ctx = mem.context("").lower()
        return sum(1 for s, _, _, _ in facts if s.lower() in ctx) / len(facts)

    def vnr_cued(mem) -> float:
        return sum(1 for s, _, _, q in facts
                   if s.lower() in mem.context(q).lower()) / len(facts)

    def vnr_recoverable(mem) -> float:
        rec_txt = mem.recoverable().lower()
        return sum(1 for s, _, _, _ in facts if s.lower() in rec_txt) / len(facts)

    print("\n== VSI: verbatim normative recall after consolidation ==")
    print(f"  RMC  active gist only:        {vnr_active(rmc):.0%}")
    print(f"  RMC  + question-cued dormant: {vnr_cued(rmc):.0%}   <- the real read path")
    print(f"  RMC  recoverable (lossless?): {vnr_recoverable(rmc):.0%}")
    print(f"  DEEP + question-cued dormant: {vnr_cued(deep):.0%}   (back-of-mind mode)")
    print(f"  DEEP recoverable (lossless?): {vnr_recoverable(deep):.0%}")
    print(f"  LossyHead (30% head):         {vnr_active(lossy):.0%}  (deleted, not recoverable)")
    print(f"  standing tokens: raw={raw_tokens}  RMC={rmc.standing_tokens()} "
          f"({rep.reduction:.0%} reduction)  DEEP={deep.standing_tokens()} "
          f"({1 - deep.standing_tokens()/raw_tokens:.0%} reduction)  "
          f"LossyHead={lossy.standing_tokens()}")

    # ----- CGW: drifted write-back must be REJECTED ---------------------- #
    def drift(gist: str) -> str:  # paraphrase a number -> verbatim invariant broken
        return re.sub(r"\b10\b", "ten", gist, count=1)

    cgw = RMCMemory(fault_hook=drift)
    cgw.ingest(list(chunks))
    cgw_rep = cgw.meditate(lookup)
    print("\n== CGW: citation-gated write-back (fault-injected paraphrase) ==")
    print(f"  committed={cgw_rep.committed}  REJECTED={cgw_rep.rejected_cgw} "
          f"(each rejection = a drifted trace refused, kept HOT for retry)")

    # ----- AAI: amendments — fresh vs stale law -------------------------- #
    amended_lookup = dict(lookup)
    for a in amendments:
        for key in list(amended_lookup):
            if key[0] == a["source"]:
                amended_lookup[key] = _ci_replace(amended_lookup[key],
                                                  a["surface_old"], a["surface_new"])
    n_inv = 0
    for a in amendments:
        n_inv += rmc.apply_amendment(a["source"], a["surface_old"], a["surface_new"],
                                     amended_lookup)
        rec.apply_amendment(a["source"], a["surface_old"], a["surface_new"],
                            amended_lookup)  # no-op by design
    rmc.meditate(amended_lookup)  # re-consolidate the invalidation queue

    def fresh_rate(mem) -> float:
        ctx = mem.context("").lower()
        return sum(1 for a in amendments if a["surface_new"].lower() in ctx) / len(amendments)

    print("\n== AAI: after the 6 real amendments (fresh-law availability) ==")
    print(f"  traces invalidated by RMC: {n_inv}")
    print(f"  RMC (amendment-aware):     serves amended law {fresh_rate(rmc):.0%}")
    print(f"  Recency baseline:          serves amended law {fresh_rate(rec):.0%} "
          f"(stale on the rest — the prior-art failure mode)")

    print("\nCaveats: deterministic mechanism demo (no LLM); token counts are "
          "chars/4 approximations; LLM-quality consolidation = step 3 on Groq.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
