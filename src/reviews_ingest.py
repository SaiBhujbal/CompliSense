"""Review ingestion pipeline for Gap Finder — pluggable, provenance-first.

Normalizes competitor reviews from any adapter into ONE schema, then produces
the quantified theme table Gap Finder needs (denominators, shares, per-theme
rating) — the "cluster → quantify" stages of research/GAP_FINDER_SPEC.md §3.

ADAPTERS (the honest part):
- CSVAdapter        WORKS TODAY. Import any exported/purchased review dataset
                    (data providers, brand-owned exports, manual collection).
- FlipkartAdapter   STUB — Flipkart's ToS prohibits scraping and its anti-bot
- NykaaAdapter      blocks make scrapers rot in days. We refuse to build the
                    product on that foundation. When you have licensed data /
                    an API/affiliate agreement, implement `fetch()` — the rest
                    of the pipeline is already done.

Theme extraction here is DETERMINISTIC keyword bucketing (stdlib, explainable,
free). Phase 2 swaps in embedding clustering (sentence-transformers is already
in this repo) behind the same `themes()` interface.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

# One normalized review = one dict with provenance. Nothing enters the
# pipeline without a source label.
SCHEMA = ("rating", "text", "date", "source", "url")

# sector -> theme -> regex. Explainable ("matched: dry"); extend per sector.
THEME_PATTERNS = {
    "electronics": {
        "call/mic quality": r"\bmic\b|call qualit|voice|caller",
        "battery": r"battery|backup|charge las|drain",
        "durability/failure": r"stopped working|one side|not working|dead|broke|faulty",
        "connectivity": r"disconnect|pairing|bluetooth|latency|lag",
        "comfort/fit": r"\bfit\b|comfort|ear pain|falls out",
    },
    "beauty": {
        "dryness/tightness": r"\bdry\b|dries|drying|tight|flak|stretch",
        "breakouts/irritation": r"break.?out|pimple|irritat|rash|burn|itch",
        "fragrance": r"smell|fragrance|scent",
        "cleansing power": r"oil control|clean[s]?e[sd]?|dirt|fresh",
    },
    "fintech": {
        "collections conduct": r"harass|recovery|calls|abuse|threat",
        "fees/charges": r"fee|charge|hidden|processing|interest",
        "support": r"support|service|response|resolve|complaint",
        "app reliability": r"crash|bug|stuck|error|otp",
    },
    "food": {
        "texture": r"hard|chewy|brick|texture|soft",
        "taste": r"taste|flavou?r|sweet|bitter|awful",
        "digestion": r"stomach|bloat|digest|gas\b",
        "freshness/leakage": r"oil|leak|melt|stale|expired",
    },
    "saas": {
        "support": r"support|ticket|response time|helpdesk",
        "complexity": r"complex|learning curve|confusing|overwhelm|clunky",
        "performance": r"slow|lag|loading|crash|bug",
        "pricing": r"price|pricing|expensive|cost",
    },
}


class CSVAdapter:
    """Import reviews from a CSV with columns: rating,text,date,source,url.
    The path every team can use today: provider exports, licensed datasets,
    or manually collected samples (label them as such)."""

    def __init__(self, path: str | Path, source_label: str = ""):
        self.path = Path(path)
        self.source_label = source_label

    def fetch(self) -> list[dict]:
        rows = []
        with open(self.path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    rating = float(r.get("rating", "") or 0)
                except ValueError:
                    rating = 0.0
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                rows.append({"rating": rating, "text": text,
                             "date": (r.get("date") or "").strip(),
                             "source": (r.get("source") or self.source_label or self.path.name).strip(),
                             "url": (r.get("url") or "").strip()})
        return rows


class _ToSBlockedAdapter:
    site = ""
    why = ""

    def fetch(self) -> list[dict]:
        raise NotImplementedError(
            f"{self.site} scraping is deliberately NOT implemented: {self.why} "
            "Use CSVAdapter with licensed/exported data, or implement fetch() "
            "once you have an API/affiliate/data agreement — the rest of the "
            "pipeline (normalize → themes → quantify) already works.")


class FlipkartAdapter(_ToSBlockedAdapter):
    site = "Flipkart"
    why = ("Flipkart's Terms of Use prohibit automated scraping, and its "
           "anti-bot rotates aggressively — scraper code rots in days and "
           "puts a trust-first product on a legally exposed foundation.")


class NykaaAdapter(_ToSBlockedAdapter):
    site = "Nykaa"
    why = ("Nykaa's ToS prohibits automated extraction; same exposure and "
           "fragility as Flipkart. Licensed data or partner API only.")


def themes(reviews: list[dict], sector: str) -> dict:
    """Quantified theme table with DENOMINATORS — never 'many reviews say'.

    Returns {"n", "negative_n", "themes": [{theme, n, share_of_negative_pct,
    avg_rating, matched_example, sources}]}. share is computed over NEGATIVE
    (<=2 star) reviews when ratings exist, else over all (flagged)."""
    pats = THEME_PATTERNS.get(sector)
    if not pats:
        raise ValueError(f"unknown sector '{sector}' — add THEME_PATTERNS for it")
    n = len(reviews)
    rated = [r for r in reviews if r["rating"] > 0]
    neg = [r for r in rated if r["rating"] <= 2] if rated else reviews
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in neg:
        tl = r["text"].lower()
        for theme, pat in pats.items():
            if re.search(pat, tl):
                buckets[theme].append(r)
    out = []
    for theme, hits in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        ratings = [h["rating"] for h in hits if h["rating"] > 0]
        out.append({
            "theme": theme, "n": len(hits),
            "share_of_negative_pct": round(100 * len(hits) / max(len(neg), 1)),
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
            "matched_example": hits[0]["text"][:140],
            "sources": sorted({h["source"] for h in hits}),
        })
    return {"n": n, "negative_n": len(neg),
            "denominator": "negative (<=2-star) reviews" if rated else "ALL reviews (no ratings in data - flagged)",
            "themes": out}


if __name__ == "__main__":
    import sys
    path, sector = sys.argv[1], sys.argv[2]
    print(json.dumps(themes(CSVAdapter(path).fetch(), sector), indent=1, ensure_ascii=False))
