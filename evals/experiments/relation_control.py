"""
MECHANISM test: is "fact-mutability decodability" really RELATION-TYPE
classification in disguise? Within TempLAMA (explicit relation IDs + data-derived
volatility labels), compare:
  IID  : 5-fold CV with relations MIXED across folds (probe may exploit relation cues)
  OOD  : train on one set of relations, test on a DISJOINT set of held-out relations
If OOD (held-out relations) collapses toward chance while IID is above chance, the
signal is relation-bound and does NOT capture an abstract, relation-transferable
"mutability" property — which explains the earlier cross-dataset non-transfer.

All within TempLAMA. Balanced classes + ROC-AUC (imbalance-robust).
"""

from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

GROUP_A = {"P54", "P108", "P39", "P102", "P488"}  # ~99 stable
GROUP_B = {"P286", "P6", "P127", "P69"}           # ~31 stable


def build():
    ds = load_dataset("Yova/templama")["train"]
    groups = {}
    for r in ds:
        pre = r["id"].rsplit("_", 1)[0]
        ans = r.get("answer") or []
        aid = ans[0]["wikidata_id"] if ans and isinstance(ans[0], dict) else None
        g = groups.setdefault(pre, {"rel": r["relation"], "q": r["query"], "ans": set()})
        if aid:
            g["ans"].add(aid)
    rows = []  # (query, relation, label)
    for g in groups.values():
        if not g["ans"]:
            continue
        rows.append((g["q"], g["rel"], 1 if len(g["ans"]) > 1 else 0))
    return rows


def balanced_idx(labels, rng):
    labels = np.array(labels)
    i0, i1 = np.where(labels == 0)[0], np.where(labels == 1)[0]
    k = min(len(i0), len(i1))
    keep = np.concatenate([rng.choice(i0, k, False), rng.choice(i1, k, False)])
    rng.shuffle(keep)
    return keep


def main():
    import torch; torch.set_num_threads(1)
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    rng = np.random.default_rng(0)

    rows = build()
    Q = [r[0] for r in rows]; REL = np.array([r[1] for r in rows]); Y = np.array([r[2] for r in rows])
    X = enc.encode(Q, normalize_embeddings=True, show_progress_bar=False, batch_size=128)

    # IID (relations mixed), balanced
    bi = balanced_idx(Y, rng)
    auc_iid = cross_val_score(LogisticRegression(max_iter=2000), X[bi], Y[bi],
                              cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring="roc_auc").mean()

    # OOD: train on GROUP_A relations, test on GROUP_B (disjoint), balanced each side
    def grp(relset):
        idx = np.array([i for i in range(len(Y)) if REL[i] in relset])
        bi = balanced_idx(Y[idx], rng)
        return idx[bi]
    A, B = grp(GROUP_A), grp(GROUP_B)
    mA = LogisticRegression(max_iter=2000).fit(X[A], Y[A])
    mB = LogisticRegression(max_iter=2000).fit(X[B], Y[B])
    a2b = roc_auc_score(Y[B], mA.decision_function(X[B]))
    b2a = roc_auc_score(Y[A], mB.decision_function(X[A]))

    print("\n" + "=" * 60)
    print("  Is mutability-decodability just RELATION classification?")
    print("=" * 60)
    print(f"  IID  (relations mixed, balanced CV)      AUC: {auc_iid:.2f}")
    print(f"  OOD  train A-relations -> test B (held-out) AUC: {a2b:.2f}")
    print(f"  OOD  train B-relations -> test A (held-out) AUC: {b2a:.2f}")
    print(f"  chance AUC: 0.50")
    print("-" * 60)
    ood = (a2b + b2a) / 2
    print(f"  IID {auc_iid:.2f} vs OOD {ood:.2f}  | gap: {auc_iid-ood:+.2f}")
    if ood <= 0.55:
        v = "CONFIRMED: signal is RELATION-bound; collapses to ~chance on held-out relations"
    elif ood < auc_iid - 0.08:
        v = "PARTIAL: relation cues carry much of it; weak relation-transferable residue"
    else:
        v = "REFUTED: generalizes to held-out relations (abstract-ish signal)"
    print(f"  VERDICT: {v}")
    print("=" * 60)
    print(f"  (TempLAMA, MiniLM, balanced; A={sorted(GROUP_A)} B={sorted(GROUP_B)};")
    print("   pilot scale, no significance test, single encoder.)")


if __name__ == "__main__":
    main()
