"""
MCA-Reg evaluation: does routing trust by fact-mutability beat a global policy
on RBI knowledge conflict?

The applied thesis: a single global trust policy fails on one class of conflict
(prefer-context absorbs misleading evidence on STABLE facts; prefer-parametric
keeps stale weights on VOLATILE facts). Mutability-routing (MCA) should get
BOTH. Also reports the mutability-classifier accuracy honestly — it is the
system's true ceiling.

  python -m evals.mca_eval      # stdlib mechanism demo, no API/models

Falsifiable: if a global policy matches MCA, or the classifier is inaccurate,
the thesis fails. (A production run swaps in a MuLan-style mutability probe +
the real pipeline + a comparison vs TrustMargin/DynaRAG.)
"""

from __future__ import annotations

import json
from pathlib import Path

from src.arbitration import POLICIES, classify_mutability, decide

DATA = Path(__file__).parent / "dataset" / "mca_reg.jsonl"


def load():
    return [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    items = load()

    # 1) Mutability-classifier accuracy (the honest ceiling).
    correct_cls = sum(1 for it in items if classify_mutability(it["claim"]) == it["mutability"])
    cls_acc = correct_cls / len(items)

    # 2) Conflict-resolution accuracy per policy, split by scenario.
    scenarios = sorted({it["scenario"] for it in items})
    rows = {}
    for policy in POLICIES:
        per_scn = {s: [0, 0] for s in scenarios}  # [correct, total]
        total_correct = 0
        for it in items:
            chosen = decide(policy, it)
            ok = chosen.strip().lower() == it["gold_answer"].strip().lower()
            total_correct += ok
            per_scn[it["scenario"]][0] += ok
            per_scn[it["scenario"]][1] += 1
        rows[policy] = (total_correct / len(items), per_scn)

    print("\n" + "=" * 74)
    print("  MCA-Reg — mutability-conditioned arbitration on RBI knowledge conflict")
    print("=" * 74)
    print(f"  mutability-classifier accuracy: {cls_acc:.0%}  ({correct_cls}/{len(items)})"
          f"   <- the system's true ceiling")
    print("-" * 74)
    hdr = "  {:<30}{:>9}".format("policy", "overall")
    for s in scenarios:
        hdr += "{:>22}".format(s)
    print(hdr)
    print("-" * 74)
    for policy, (overall, per_scn) in rows.items():
        line = "  {:<30}{:>8.0%}".format(policy, overall)
        for s in scenarios:
            c, t = per_scn[s]
            line += "{:>22}".format(f"{c}/{t}")
        print(line)
    print("=" * 74)

    mca = rows["MCA (mutability-routed)"][0]
    best_global = max(rows[p][0] for p in rows if "global" in p)
    win = mca > best_global
    print(f"  MCA overall: {mca:.0%}   best single global policy: {best_global:.0%}")
    print(f"  RESULT: {'THESIS SUPPORTED' if win else 'THESIS NOT SUPPORTED'} — "
          f"{'mutability-routing beats every global policy' if win else 'no advantage over a global policy'}")
    print("  (demo on {} items, mechanism-level; needs real conflict benchmark + "
          "MuLan probe + TrustMargin/DynaRAG baselines)".format(len(items)))
    print("=" * 74 + "\n")


if __name__ == "__main__":
    main()
