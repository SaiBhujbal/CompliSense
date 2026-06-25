"""
REAL pilot experiment: is fact MUTABILITY linearly decodable from a model's
sentence representations — and is it more than a surface cue (numbers/dates)?

This tests the load-bearing assumption of MCA-Reg (mutability-conditioned
arbitration). If mutability is NOT decodable, the whole direction is dead.

Method: embed labeled mutable/immutable statements with a real sentence encoder,
train logistic regression with stratified CV, and compare against a SURFACE
baseline (has-digit / has-year / length) to show the signal isn't trivial.

Honest scope: small self-built set + a small CPU encoder = a PILOT, not a Q1
result. A real study needs MuLan/DYNAMICQA data, frontier-model hidden states,
and significance testing. This just checks feasibility, for real, on real data.
"""

from __future__ import annotations

import re

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

# label 0 = IMMUTABLE (stable), 1 = MUTABLE (volatile).
# Deliberately adversarial to surface cues: immutable facts that DO contain
# numbers/years, and mutable facts that do NOT — so a digit/year detector can't win.
DATA = [
    # --- IMMUTABLE, many with numbers/years (defeat the surface baseline) ---
    ("Water boils at 100 degrees Celsius at sea level.", 0),
    ("A triangle has 3 sides.", 0),
    ("The speed of light is 299792458 metres per second.", 0),
    ("World War II ended in 1945.", 0),
    ("There are 7 days in a week.", 0),
    ("The chemical symbol for gold is Au.", 0),
    ("A right angle measures 90 degrees.", 0),
    ("The freezing point of water is 0 degrees Celsius.", 0),
    ("The capital of France is Paris.", 0),
    ("The square root of 144 is 12.", 0),
    ("The human body has 206 bones in adulthood.", 0),
    ("India gained independence in 1947.", 0),
    ("The atomic number of carbon is 6.", 0),
    ("A leap year has 366 days.", 0),
    ("The Pacific is the largest ocean on Earth.", 0),
    ("Mount Everest is the highest mountain above sea level.", 0),
    ("The first man on the Moon landed in 1969.", 0),
    ("An octagon has 8 sides.", 0),
    ("The boiling point of nitrogen is about minus 196 degrees Celsius.", 0),
    ("The Great Wall of China was built over many centuries.", 0),
    ("A dozen equals 12 items.", 0),
    ("Photosynthesis converts sunlight into chemical energy.", 0),
    ("The Pythagorean theorem relates the sides of a right triangle.", 0),
    ("DNA carries genetic information in living organisms.", 0),
    ("The Earth orbits the Sun.", 0),
    # --- MUTABLE, many WITHOUT explicit numbers (defeat the surface baseline) ---
    ("The current Prime Minister of India is in office.", 1),
    ("The reigning Wimbledon men's singles champion holds the title.", 1),
    ("The latest flagship iPhone is the newest model on sale.", 1),
    ("The present Governor of the Reserve Bank of India leads the central bank.", 1),
    ("The current world's tallest building is the tallest completed tower.", 1),
    ("Today's weather in Mumbai is the current condition outside.", 1),
    ("The best-selling car model this year leads the market.", 1),
    ("The current champions of the Indian Premier League hold the trophy.", 1),
    ("The latest version of Python is the newest stable release.", 1),
    ("The current CEO of the company runs day-to-day operations.", 1),
    ("The repo rate set by the central bank is 6.5 percent.", 1),
    ("The current population of India is about 1.4 billion.", 1),
    ("The price of gold today is around 7000 rupees per gram.", 1),
    ("The latest GDP growth rate was 7.2 percent.", 1),
    ("The current exchange rate is about 86 rupees per US dollar.", 1),
    ("The minimum net owned fund requirement is 10 crore.", 1),
    ("The co-lending retention requirement is 10 percent.", 1),
    ("The current inflation rate stands near 5 percent.", 1),
    ("The number of active users on the platform is rising.", 1),
    ("The current market leader in UPI payments dominates volume.", 1),
    ("The reigning Formula One world champion holds the title.", 1),
    ("The newest model from the AI lab is the latest release.", 1),
    ("The current finance minister presents the annual budget.", 1),
    ("The top-ranked tennis player leads the rankings.", 1),
    ("The current stock price of the firm reflects today's trading.", 1),
]

_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_DIGIT = re.compile(r"\d")


def surface_features(text: str) -> list[float]:
    return [
        float(bool(_DIGIT.search(text))),
        float(bool(_YEAR.search(text))),
        float(len(text.split())),
        float("current" in text.lower() or "latest" in text.lower() or "today" in text.lower()),
    ]


def main() -> None:
    texts = [t for t, _ in DATA]
    y = np.array([lab for _, lab in DATA])
    print(f"\nDataset: {len(texts)} statements  ({int((y==0).sum())} immutable, {int((y==1).sum())} mutable)")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)

    # --- Surface baseline (is mutability just 'has a number/year'?) ---
    Xs = np.array([surface_features(t) for t in texts])
    surf = cross_val_score(LogisticRegression(max_iter=1000), Xs, y, cv=cv, scoring="accuracy")

    # --- Real embedding probe ---
    from sentence_transformers import SentenceTransformer

    print("Loading encoder (downloads once)...")
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    Xe = enc.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    emb = cross_val_score(LogisticRegression(max_iter=2000), Xe, y, cv=cv, scoring="accuracy")

    print("\n" + "=" * 64)
    print("  Mutability probe — is fact volatility decodable?")
    print("=" * 64)
    print(f"  Surface baseline (digit/year/len/'current'): {surf.mean():.1%}  (+/- {surf.std():.1%})")
    print(f"  Embedding probe (MiniLM + logreg):           {emb.mean():.1%}  (+/- {emb.std():.1%})")
    print(f"  Majority-class floor:                        {max((y==0).mean(),(y==1).mean()):.1%}")
    print("-" * 64)
    delta = emb.mean() - surf.mean()
    print(f"  embedding - surface: {delta:+.1%}")
    if emb.mean() >= 0.8 and delta > 0.05:
        verdict = "DECODABLE & beyond surface cues -> MCA-Reg assumption holds (pilot)"
    elif emb.mean() >= 0.8:
        verdict = "DECODABLE but may be surface-driven -> needs adversarial data"
    else:
        verdict = "NOT reliably decodable here -> assumption at risk"
    print(f"  PILOT VERDICT: {verdict}")
    print("=" * 64)
    print("  Caveat: small self-built set + small CPU encoder. Real study needs"
          "\n  MuLan/DYNAMICQA data, frontier-model representations, significance tests.\n")


if __name__ == "__main__":
    main()
