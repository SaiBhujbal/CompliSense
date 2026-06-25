"""
NOVELTY-HUNTING measurement (not a confirmation demo): does the "fact mutability"
signal TRANSFER across datasets AND across labeling methods?

Prior work (MuLan, DYNAMICQA) measures mutability decodability WITHIN one dataset
with template/curated labels. Nobody (found) tests whether a probe trained on one
corpus generalizes to a DIFFERENT corpus whose labels are DATA-DERIVED. If it
transfers -> mutability is a robust, model-intrinsic, label-method-independent
property (strong finding). If it collapses -> it's a dataset/relation artifact
(also a finding, and an important caution for anyone building on it).

Datasets:
  DYNAMICQA (copenlu/dynamicqa): static(0) vs temporal(1) — template labels.
  TempLAMA  (Yova/templama): label DATA-DERIVED = #distinct answers over years
            (>1 => mutable=1, ==1 => stable=0).

Probe: MiniLM query/question embedding -> logistic regression. We report
within-dataset CV AND cross-dataset transfer BOTH directions.
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

PER_CLASS = 600


def balance(items_by_label, per_class, rng):
    out_t, out_y = [], []
    for lab, texts in items_by_label.items():
        rng.shuffle(texts)
        for t in texts[:per_class]:
            out_t.append(t); out_y.append(lab)
    return out_t, out_y


def build_dynamicqa(rng):
    by = {0: [], 1: []}
    for cfg, lab in [("static", 0), ("temporal", 1)]:
        ds = load_dataset("copenlu/dynamicqa", cfg)["test"]
        by[lab] = [r["question"] for r in ds]
    return balance(by, PER_CLASS, rng)


def build_templama(rng):
    ds = load_dataset("Yova/templama")["train"]
    groups = {}  # entity_relation -> {"query":..., "answers":set()}
    for r in ds:
        rid = r["id"]
        prefix = rid.rsplit("_", 1)[0]
        ans = r.get("answer") or []
        aid = ans[0]["wikidata_id"] if ans and isinstance(ans[0], dict) else None
        g = groups.setdefault(prefix, {"query": r["query"], "answers": set()})
        if aid:
            g["answers"].add(aid)
    by = {0: [], 1: []}
    for g in groups.values():
        if not g["answers"]:
            continue
        lab = 1 if len(g["answers"]) > 1 else 0  # changed over time => mutable
        by[lab].append(g["query"])
    return balance(by, PER_CLASS, rng)


def main():
    import torch; torch.set_num_threads(1)
    from sentence_transformers import SentenceTransformer
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    rng = np.random.default_rng(0)

    dq_t, dq_y = build_dynamicqa(rng)
    tl_t, tl_y = build_templama(rng)

    # BALANCE both sets to their minority class so accuracy is meaningful (chance=50%).
    def rebalance(texts, ys, rng):
        ys = np.array(ys); idx0 = np.where(ys == 0)[0]; idx1 = np.where(ys == 1)[0]
        k = min(len(idx0), len(idx1))
        keep = np.concatenate([rng.choice(idx0, k, replace=False), rng.choice(idx1, k, replace=False)])
        rng.shuffle(keep)
        return [texts[i] for i in keep], ys[keep]
    dq_t, ydq = rebalance(dq_t, dq_y, rng)
    tl_t, ytl = rebalance(tl_t, tl_y, rng)
    print(f"DYNAMICQA(bal): {len(ydq)} ({int((ydq==0).sum())}/{int((ydq==1).sum())})  "
          f"TempLAMA(bal): {len(ytl)} ({int((ytl==0).sum())}/{int((ytl==1).sum())})", flush=True)

    Xdq = enc.encode(dq_t, normalize_embeddings=True, show_progress_bar=False, batch_size=128)
    Xtl = enc.encode(tl_t, normalize_embeddings=True, show_progress_bar=False, batch_size=128)
    cv = StratifiedKFold(5, shuffle=True, random_state=0)

    within_dq = cross_val_score(LogisticRegression(max_iter=2000), Xdq, ydq, cv=cv, scoring="roc_auc").mean()
    within_tl = cross_val_score(LogisticRegression(max_iter=2000), Xtl, ytl, cv=cv, scoring="roc_auc").mean()

    # cross-transfer: train on one, test on the other (report accuracy AND AUC)
    m_d = LogisticRegression(max_iter=2000).fit(Xdq, ydq)
    m_t = LogisticRegression(max_iter=2000).fit(Xtl, ytl)
    dq2tl = m_d.score(Xtl, ytl); dq2tl_auc = roc_auc_score(ytl, m_d.decision_function(Xtl))
    tl2dq = m_t.score(Xdq, ydq); tl2dq_auc = roc_auc_score(ydq, m_t.decision_function(Xdq))

    print("\n" + "=" * 64)
    print("  Mutability-probe TRANSFER (balanced; AUC imbalance-robust)")
    print("=" * 64)
    print(f"  within DYNAMICQA (template labels)  AUC: {within_dq:.2f}")
    print(f"  within TempLAMA  (data-derived)     AUC: {within_tl:.2f}")
    print(f"  TRANSFER DYNAMICQA->TempLAMA: acc {dq2tl:.0%}  AUC {dq2tl_auc:.2f}")
    print(f"  TRANSFER TempLAMA->DYNAMICQA: acc {tl2dq:.0%}  AUC {tl2dq_auc:.2f}")
    print(f"  chance: acc 50%, AUC 0.50")
    print("-" * 64)
    avg_within = (within_dq + within_tl) / 2
    avg_trans = (dq2tl_auc + tl2dq_auc) / 2
    drop = avg_within - avg_trans
    print(f"  avg within: {avg_within:.1%} | avg transfer: {avg_trans:.1%} | drop: {drop:+.1%}")
    if avg_trans >= 0.65:
        v = "TRANSFERS -> mutability is a robust, label-method-independent signal (finding)"
    elif avg_trans >= 0.55:
        v = "PARTIAL transfer -> shared but not fully portable signal"
    else:
        v = "COLLAPSES -> mutability decodability is largely dataset/label artifact (cautionary finding)"
    print(f"  VERDICT: {v}")
    print("=" * 60)
    print("  Caveat: small CPU encoder; query templates carry relation cues; my")
    print("  TempLAMA label = #distinct answers over years. A real study needs")
    print("  frontier-model reps, entity-masking controls, significance tests.")


if __name__ == "__main__":
    main()
