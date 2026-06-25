"""
NRuC — Nuance-Recovery under Consolidation.

The killer comparison for the "back-of-the-mind" memory thesis: when
consolidation removes a conditional carve-out from active context, does a later
cue recover it? Lossy reflection (gist replaces detail) should FAIL; DT-CAM
(demote-not-delete + cue recovery) should PASS — at comparable standing token
cost. An ablation (DT-CAM with cue recovery OFF) isolates whether associative
recovery, not just storage, carries the gain.

  python -m evals.nruc_eval

Runs with NO API keys / models (stdlib mechanism demo). Falsifiable: if lossy
also recovers, or DT-CAM's standing cost balloons, the thesis is wrong.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.memory import DualTraceMemory, LossyReflectionMemory

DATA = Path(__file__).parent / "dataset" / "nruc.jsonl"


def load():
    return [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def evaluate(memory_factory):
    items = load()
    recovered = lost = 0
    standing, perquery = [], []
    detail = []
    for it in items:
        mem = memory_factory()
        mem.ingest_and_consolidate([it["passage"]])
        phrase = it["conditional_phrase"].lower()
        ctx = mem.context_for(it["cue_query"]).lower()
        is_recovered = phrase in ctx
        is_lost = phrase not in mem.recoverable_corpus().lower()
        recovered += is_recovered
        lost += is_lost
        standing.append(mem.standing_tokens())
        perquery.append(mem.query_tokens(it["cue_query"]))
        detail.append((it["id"], is_recovered, is_lost))
    n = len(items)
    return {
        "n": n,
        "NRR": recovered / n,                 # nuance-recovery rate (primary)
        "permanent_loss_rate": lost / n,      # nuance deleted forever
        "mean_standing_tokens": sum(standing) / n,
        "mean_query_tokens": sum(perquery) / n,
        "detail": detail,
    }


def main() -> None:
    configs = {
        "Lossy reflection (baseline)": lambda: LossyReflectionMemory(),
        "DT-CAM (dual-trace)": lambda: DualTraceMemory(use_cue_recovery=True),
        "DT-CAM ablation (no cue recovery)": lambda: DualTraceMemory(use_cue_recovery=False),
    }
    results = {name: evaluate(f) for name, f in configs.items()}

    print("\n" + "=" * 72)
    print("  NRuC — Nuance-Recovery under Consolidation")
    print("=" * 72)
    print(f"  {'memory':<36}{'NRR':>7}{'perm-loss':>11}{'stand-tok':>11}{'q-tok':>7}")
    print("-" * 72)
    for name, r in results.items():
        print(f"  {name:<36}{r['NRR']:>6.0%}{r['permanent_loss_rate']:>11.0%}"
              f"{r['mean_standing_tokens']:>11.1f}{r['mean_query_tokens']:>7.1f}")
    print("-" * 72)

    base = results["Lossy reflection (baseline)"]
    dt = results["DT-CAM (dual-trace)"]
    abl = results["DT-CAM ablation (no cue recovery)"]
    print("  per-item recovery (recovered / permanently-lost):")
    for (iid, rec, lost), (_, drec, dlost) in zip(base["detail"], dt["detail"]):
        print(f"    {iid:<20} lossy={'rec' if rec else 'LOST' if lost else 'miss':<5}"
              f"  dt-cam={'rec' if drec else 'miss'}")
    print("=" * 72)
    gap = dt["NRR"] - base["NRR"]
    overhead = (dt["mean_standing_tokens"] / base["mean_standing_tokens"]) if base["mean_standing_tokens"] else 1
    cue_effect = dt["NRR"] - abl["NRR"]
    verdict = (
        gap > 0.3 and base["permanent_loss_rate"] > 0.5
        and dt["permanent_loss_rate"] < 0.2 and overhead < 1.6
    )
    print(f"  recovery gap (DT-CAM - lossy): {gap:+.0%}")
    print(f"  DT-CAM permanent loss: {dt['permanent_loss_rate']:.0%}  vs lossy: {base['permanent_loss_rate']:.0%}")
    print(f"  standing-token overhead vs lossy: {overhead:.2f}x")
    print(f"  cue-recovery contribution (DT-CAM - ablation NRR): {cue_effect:+.0%}  (ablation check)")
    print("=" * 72)
    print(f"  RESULT: {'THESIS SUPPORTED' if verdict else 'THESIS NOT SUPPORTED'} "
          f"(demo on {base['n']} items; mechanism-level, not LLM/embedding)")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
