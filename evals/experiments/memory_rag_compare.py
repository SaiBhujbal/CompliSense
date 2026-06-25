"""
REAL comparison (CPU, real MiniLM embeddings): DT-CAM ("meditation"/long-term
memory RAG) vs the memory/RAG baselines it competes with, on a SCALING corpus.

Robust version: all text is embedded in ONE batch up front (repeated encode()
calls segfault torch on CPU), threads capped for stability.

Systems (fixed per-query context budget; growing distractor corpus = long-term pressure):
  FIFO-Truncation : keep most-recent docs up to budget (long-context-window limit)
  SummaryMemory   : reflection-style lossy consolidation — keep each doc's MAIN
                    normative clause, DROP the subordinate conditional nuance
  VanillaRAG      : real dense top-k retrieval from the full corpus
  DT-CAM          : conditional spans demoted to a dormant tier (0 standing cost),
                    cue-recovered by dense similarity (real embeddings)
Metric: nuance-recall@context (is the answer-bearing conditional in final context?).
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

BUDGET = 1200  # per-query / active context budget (chars//4 approx)
CORPUS_SIZES = [0, 40, 120, 280]

_BASE = [
    ("Each co-lender must retain at least 10% of every loan",
     "but the originator may also provide a default loss guarantee of up to 5% as an extra cushion"),
    ("A single borrower's exposure is capped at Rs 50,000 across P2P platforms",
     "but a lender deploying over Rs 10 lakh must additionally furnish a net worth certificate"),
    ("Loan disbursals must go directly to the borrower's bank account",
     "except in co-lending or specific mandated end-use where alternate routing is allowed"),
    ("The board must approve the compliance policy annually",
     "but the board may delegate operational approvals to a committee where workload requires"),
    ("Entities shall file the quarterly return by the stipulated date",
     "though smaller entities below the threshold may optionally adopt a simplified format"),
]
TARGETS = []  # (main, conditional, query)
for i, (m, c) in enumerate((_BASE * 4)[:20]):
    s = f" [clause {i+1}]"
    TARGETS.append((m + s, c + s, f"what optional or exceptional extra applies to: {m.lower()}{s}?"))

_DTPL = [
    "This circular consolidates earlier guidance for the sector under reference {n}.",
    "Regulated entities should review internal processes per note {n}.",
    "The framework promotes transparency and orderly conduct, item {n}.",
    "Stakeholders were consulted in preparing annexure {n}.",
    "General governance and reporting provisions appear in section {n}.",
]
DISTRACTORS = [_DTPL[j % len(_DTPL)].format(n=j) for j in range(max(CORPUS_SIZES))]


def toks(s: str) -> int:
    return max(1, len(s) // 4)


def main() -> None:
    import torch
    torch.set_num_threads(1)
    from sentence_transformers import SentenceTransformer

    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")

    target_full = [f"{m}. {c}." for (m, c, _) in TARGETS]
    target_main = [m for (m, _, _) in TARGETS]
    target_cond = [c for (_, c, _) in TARGETS]
    queries = [q for (_, _, q) in TARGETS]
    cond_key = [c.lower()[:35] for c in target_cond]

    # ONE batch encode of every unique string we need.
    alltxt = target_full + target_cond + queries + DISTRACTORS
    E = enc.encode(alltxt, normalize_embeddings=True, show_progress_bar=False, batch_size=128)
    n_t = len(target_full)
    Ef = E[:n_t]
    Ec = E[n_t:2 * n_t]
    Eq = E[2 * n_t:3 * n_t]
    Ed = E[3 * n_t:]

    def recall(ctx_per_q):
        return sum(cond_key[i] in ctx_per_q[i].lower() for i in range(n_t)) / n_t

    print(f"{'corpus':>8}{'FIFO':>10}{'SummaryMem':>12}{'VanillaRAG':>12}{'DT-CAM':>10}   nuance-recall@ctx")
    standing = {}
    for n in CORPUS_SIZES:
        d_txt = DISTRACTORS[:n]
        Edn = Ed[:n]
        # corpus order: targets interleaved, then distractors appended (targets are "older")
        corpus_txt = target_full + d_txt

        # FIFO: most-recent (end) up to budget
        ctx, b = [], 0
        for t in reversed(corpus_txt):
            if b + toks(t) > BUDGET:
                break
            ctx.append(t); b += toks(t)
        fifo = recall([" ".join(ctx)] * n_t)

        # SummaryMemory: keep MAIN clause of targets + distractor sentence; drop conditionals
        gists = target_main + d_txt
        ctx, b = [], 0
        for g in gists:
            if b + toks(g) > BUDGET:
                break
            ctx.append(g); b += toks(g)
        summ = recall([" ".join(ctx)] * n_t)

        # VanillaRAG: dense top-k over full docs into budget, per query
        Dmat = np.vstack([Ef, Edn]) if n else Ef
        Dtxt = corpus_txt
        van_ctx = []
        for qi in range(n_t):
            order = np.argsort(-(Dmat @ Eq[qi]))
            c, b = [], 0
            for idx in order:
                if b + toks(Dtxt[idx]) > BUDGET:
                    break
                c.append(Dtxt[idx]); b += toks(Dtxt[idx])
            van_ctx.append(" ".join(c))
        van = recall(van_ctx)

        # DT-CAM: dormant = conditional spans only; cue-recover by similarity
        dt_ctx = []
        for qi in range(n_t):
            order = np.argsort(-(Ec @ Eq[qi]))
            c, b = [], 0
            for idx in order:
                if b + toks(target_cond[idx]) > BUDGET:
                    break
                c.append(target_cond[idx]); b += toks(target_cond[idx])
            dt_ctx.append(" ".join(c))
        dt = recall(dt_ctx)

        print(f"{n:>8}{fifo:>9.0%}{summ:>12.0%}{van:>12.0%}{dt:>10.0%}")
        standing = {
            "FIFO": min(BUDGET, sum(toks(t) for t in corpus_txt)),
            "SummaryMem": min(BUDGET, sum(toks(g) for g in gists)),
            "VanillaRAG": 0,
            "DT-CAM": n_t * 6,  # ~6-token stub per demoted conditional, in active gist
        }

    print("\nStanding (resident) active-context tokens @ largest corpus:")
    for k, v in standing.items():
        print(f"  {k:<12} ~{v}")


if __name__ == "__main__":
    main()
