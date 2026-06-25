"""
NRPC evaluation: token-reduction-AT-FIXED-RECALL — the core research measurement.

For each benchmark obligation we build a realistic "retrieved context" (the
normative obligation sentence(s) embedded in RBI-style boilerplate), run NRPC,
and check (a) how many tokens were saved and (b) whether EVERY normative key
fact survived. The thesis passes only if recall stays at 100% while tokens drop.

Runs with NO API keys / corpus (rule-based + stdlib).

  python -m evals.nrpc_eval                 # keep_ratio=0.0 (max compression)
  python -m evals.nrpc_eval --keep-ratio 0.15

HONEST SCOPE: this demonstrates the *mechanism* on constructed contexts where
normative=obligation and the rest is boilerplate. Real-corpus validation (NRPC
on actual RBI chunks + measuring the LLM answer's recall via run_eval) is the
next step.
"""

from __future__ import annotations

import argparse

from src.rag.compression import compress_context

from .run_eval import load_items

# Genuinely non-normative filler (no modal/number/date/section markers).
BOILERPLATE = [
    "This circular consolidates earlier guidance issued to the sector.",
    "Regulated entities are encouraged to familiarise themselves with the framework.",
    "The Reserve Bank may issue clarifications from time to time.",
    "This document aims to promote transparency and orderly growth of the ecosystem.",
    "Stakeholders have been consulted in the preparation of this note.",
    "The broader intent is to protect the interests of customers and the wider system.",
]


def build_context(obligation_sentences: list[str]) -> str:
    """Interleave normative obligation sentences with boilerplate noise."""
    parts: list[str] = []
    for i, sent in enumerate(obligation_sentences):
        parts.append(BOILERPLATE[(2 * i) % len(BOILERPLATE)])
        parts.append(BOILERPLATE[(2 * i + 1) % len(BOILERPLATE)])
        parts.append(sent)
    parts.extend(BOILERPLATE)
    return " ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-ratio", type=float, default=0.0,
                    help="fraction of non-normative tokens to retain (0 = max compression)")
    args = ap.parse_args()

    items = [
        it for it in load_items()
        if any(ob.key_facts for ob in it.required_obligations)
    ]

    total_facts = retained_facts = 0
    reductions: list[float] = []
    rows = []

    for it in items:
        obligations = [ob for ob in it.required_obligations if ob.key_facts]
        context = build_context([ob.summary for ob in obligations])
        compressed, stats = compress_context(context, keep_ratio=args.keep_ratio)
        low = compressed.lower()

        item_total = item_kept = 0
        missing = []
        for ob in obligations:
            for kf in ob.key_facts:
                item_total += 1
                if kf.lower() in low:
                    item_kept += 1
                else:
                    missing.append(f"{ob.id}:{kf}")
        total_facts += item_total
        retained_facts += item_kept
        reductions.append(stats.reduction)
        rows.append((it.id, stats.reduction, item_kept, item_total, missing))

    print("\n" + "=" * 64)
    print("  NRPC — token reduction at fixed recall")
    print(f"  keep_ratio={args.keep_ratio}")
    print("=" * 64)
    for iid, red, kept, tot, missing in rows:
        tag = "ok" if kept == tot else f"MISSING={missing}"
        print(f"  {iid:<14} reduction={red:5.1%}  recall={kept}/{tot}  {tag}")
    print("-" * 64)
    macro_reduction = sum(reductions) / len(reductions) if reductions else 0.0
    recall = retained_facts / total_facts if total_facts else 1.0
    print(f"  mean token reduction:        {macro_reduction:6.1%}")
    print(f"  normative key-fact recall:   {recall:6.1%}  (must be 100% to ship)")
    print("=" * 64)
    ok = recall >= 1.0
    print(f"  RESULT: {'PASS' if ok else 'FAIL'} — "
          f"{'tokens cut with zero normative loss' if ok else 'a normative fact was dropped'}")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
