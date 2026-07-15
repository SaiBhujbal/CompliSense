"""Competitor/sector news pipeline — the event layer for Gap Finder & lenses.

Fetches Google News RSS for a competitor or sector query (ToS-fine: public RSS,
attributed links out to the original publisher), tiers every item by SOURCE
QUALITY, and tags the EVENT TYPE (funding, pricing, recall, regulatory, ...).
This is what lets sentiment/gap findings be tied to events ("rating fell the
week they raised fees") instead of floating vibes.

Deliberately DETERMINISTIC and pure stdlib (urllib + ElementTree + re + json),
same pattern as watchtower.py — safe to import in server.py (no torch), free
to run, and every tag is explainable ("matched: penalty").

Trust rules baked in:
- every item carries its publisher + link (provenance, always)
- source tiers are explicit; tier-3 social/blog noise is EXCLUDED by default
- nothing here is a claim — it's leads for the agents to verify and cite
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

_CACHE = Path(__file__).parent.parent / "data" / "newsfeed_cache.json"
_TTL_S = 600  # Google News RSS is fine with polite intervals; 10-min cache
_UA = {"User-Agent": "Mozilla/5.0 (CompliSense NewsFeed)"}

# ---- source quality tiers (verifiable > press > everything else) ----------
_TIER1 = r"rbi\.org|sebi\.gov|mca\.gov|pib\.gov|bseindia|nseindia|gazette"          # regulator / filing
_TIER2 = (r"economictimes|livemint|business.?standard|moneycontrol|reuters|"
          r"bloomberg|financialexpress|thehindubusinessline|cnbctv18|ndtvprofit|"
          r"techcrunch|inc42|entrackr|yourstory|the.?ken|morning.?context")           # business press
# everything else = tier 3 (blogs/aggregators/social) — excluded unless asked

# ---- event tagging (explainable, drives "what changed" linking) -----------
_EVENTS = [
    ("regulatory", r"\brbi\b|sebi|penalt|fine[sd]?\b|show.?cause|complian|licen[cs]e|ban\b|banned|regulator"),
    ("funding",    r"raises?|funding|series [a-h]\b|valuation|ipo\b|acquisition|acquire[sd]?|merger|stake"),
    ("pricing",    r"price hike|price cut|fee[s]?\b|charge[s]?\b|subscription|tariff|discount"),
    ("product",    r"launch|unveil|new (product|model|app|feature)|recall|discontinue[sd]?"),
    ("leadership", r"ceo|cfo|founder|resign|appoint|steps down|exit[s]?\b"),
    ("distress",   r"layoff|lay.?off|shut[s]? down|losses|loss widens|default|insolven|fraud"),
]


def _tier(link: str, source: str) -> int:
    hay = f"{link} {source}".lower()
    if re.search(_TIER1, hay):
        return 1
    if re.search(_TIER2, hay):
        return 2
    return 3


def _events(title: str) -> list[dict]:
    tl = title.lower()
    out = []
    for name, pat in _EVENTS:
        m = re.findall(pat, tl)
        if m:
            out.append({"type": name, "matched": sorted(set(x if isinstance(x, str) else x[0] for x in m))[:3]})
    return out


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save_cache(c: dict) -> None:
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def get_news(query: str, limit: int = 20, include_tier3: bool = False) -> dict:
    """News leads for a competitor/sector query, tiered + event-tagged.

    Returns {"query", "items": [{title, link, source, date, tier, events}],
    "checked_at", "cached"}. Items are LEADS for agents to verify, not claims.
    """
    query = (query or "").strip()
    if not query:
        return {"query": "", "items": [], "error": "empty query"}
    key = f"{query.lower()}|{int(include_tier3)}"
    cache = _load_cache()
    hit = cache.get(key)
    now = time.time()
    if hit and now - hit.get("ts", 0) < _TTL_S:
        return {**hit["data"], "cached": True}

    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query)
           + "&hl=en-IN&gl=IN&ceid=IN:en")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        xml_text = r.read().decode("utf-8", "ignore")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|#)", "&amp;", xml_text)
        root = ET.fromstring(xml_text)

    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        date = (it.findtext("pubDate") or "").strip()
        src_el = it.find("{*}source") if hasattr(it, "find") else None
        source = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
        if not source and " - " in title:  # Google News appends "Title - Publisher"
            title, source = title.rsplit(" - ", 1)
        if not title:
            continue
        tier = _tier(link, source)
        if tier == 3 and not include_tier3:
            continue
        items.append({"title": title, "link": link, "source": source,
                      "date": date, "tier": tier, "events": _events(title)})
        if len(items) >= limit:
            break

    data = {"query": query, "items": items,
            "checked_at": time.strftime("%Y-%m-%d %H:%M", time.localtime()),
            "note": "tier1=regulator/filing, tier2=business press; tier3 excluded by default. Leads to verify, not claims."}
    cache[key] = {"ts": now, "data": data}
    _save_cache(cache)
    return {**data, "cached": False}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "boAt earbuds"
    out = get_news(q)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:4000])
