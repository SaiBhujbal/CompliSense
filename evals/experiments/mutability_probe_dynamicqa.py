"""
REAL-DATA replication of the mutability probe on DYNAMICQA (copenlu/dynamicqa).

This removes the self-built-data caveat from mutability_probe.py. DYNAMICQA labels
facts as static (immutable) vs temporal (mutable) based on Wikidata edit history —
NOT on surface wording (the question is an identical template across both classes).
So this is a much harder, surface-controlled test. We probe three signals with
5-fold CV logistic regression:
  A) question embedding (template-identical -> should be ~chance if honest)
  B) context embedding (descriptive sentence -> may carry distributional cues)
  C) subject-popularity metadata baseline (trivial control)

Whatever the numbers are, we report them straight. A near-chance result HONESTLY
tempers the inflated 98% from the toy set and shows why frontier-model hidden
states (MuLan's actual method) are needed — which we cannot run here on CPU.
"""

from __future__ import annotations

import numpy as np
from datasets import load_dataset
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

N_PER_CLASS = 800


def sample(cfg: str, label: int, n: int):
    ds = load_dataset("copenlu/dynamicqa", cfg)["test"]
    n = min(n, ds.num_rows)
    rows = ds.select(range(n))
    return (
        [r["question"] for r in rows],
        [r["context"] for r in rows],
        [float(r.get("s_pop") or 0) for r in rows],
        [label] * n,
    )


def cv(X, y, label):
    X = np.asarray(X)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    s = cross_val_score(LogisticRegression(max_iter=2000), X, np.asarray(y),
                        cv=StratifiedKFold(5, shuffle=True, random_state=0), scoring="accuracy")
    print(f"  {label:<42}{s.mean():.1%}  (+/- {s.std():.1%})")
    return s.mean()


def main() -> None:
    q0, c0, p0, y0 = sample("static", 0, N_PER_CLASS)
    q1, c1, p1, y1 = sample("temporal", 1, N_PER_CLASS)
    q, c, p, y = q0 + q1, c0 + c1, p0 + p1, y0 + y1
    print(f"\nDYNAMICQA balanced sample: {len(y)}  ({y.count(0)} static/immutable, {y.count(1)} temporal/mutable)")

    from sentence_transformers import SentenceTransformer
    print("Encoding with MiniLM (CPU)...")
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    Xq = enc.encode(q, normalize_embeddings=True, show_progress_bar=False, batch_size=64)
    Xc = enc.encode(c, normalize_embeddings=True, show_progress_bar=False, batch_size=64)

    print("\n" + "=" * 62)
    print("  Mutability probe on REAL DYNAMICQA (5-fold CV)")
    print("=" * 62)
    print(f"  majority-class floor:                     {max(np.mean(y), 1-np.mean(y)):.1%}")
    a = cv(Xq, y, "A) question embedding (surface-controlled)")
    b = cv(Xc, y, "B) context embedding")
    pb = cv(p, y, "C) subject-popularity metadata baseline")
    print("=" * 62)
    best = max(a, b)
    if best < 0.6:
        v = "mutability NOT decodable from surface text here (honest, sobering)"
    elif best < 0.75:
        v = "weak/distributional signal only — far below the toy 98%"
    else:
        v = "decodable even surface-controlled (notable)"
    print(f"  VERDICT: {v}")
    print("  Note: MuLan's claim is about FRONTIER-MODEL HIDDEN STATES, not a")
    print("  small sentence encoder of the text. That probe needs compute we lack.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
