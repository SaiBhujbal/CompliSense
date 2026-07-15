"""RBI Watchtower — the productized AAI engine (MVP).

Monitors RBI's official RSS feeds (notifications + press releases), detects new
items, and maps each to the subscriber profiles it affects, with a severity
read. Deliberately DETERMINISTIC for the MVP: keyword/regex relevance + rule
severity = fast, free, and explainable ("matched: digital lending, DLG").
Phase 2 adds an LLM impact summary per NEW circular (one call per circular,
not per user) and email delivery.

Pure stdlib (urllib + ElementTree + re + json) — safe to import in server.py
(no torch/chromadb), works on free infra.
"""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

FEEDS = {
    "notification": "https://www.rbi.org.in/notifications_rss.xml",
    "press_release": "https://www.rbi.org.in/pressreleases_rss.xml",
}
_STATE = Path(__file__).parent.parent / "data" / "watchtower_state.json"
_UA = {"User-Agent": "Mozilla/5.0 (CompliSense Watchtower)"}

# Profile -> regex terms that make an item relevant to that subscriber profile.
PROFILES = {
    "lending": r"digital lending|nbfc|lending service provider|\bdlg\b|default loss guarantee|co.?lending|microfinance|micro finance|priority sector|credit|loan",
    "payments": r"payment aggregator|payment gateway|payments? bank|\bupi\b|prepaid|\bppi\b|wallet|settlement|payment system|card|tokeni[sz]ation",
    "p2p": r"peer.?to.?peer|\bp2p\b|nbfc.?p2p",
    "aa_data": r"account aggregator|data localis|data protection|consent|digital personal data|outsourcing|information technology|cyber",
    "markets_fx": r"foreign exchange|\bfema\b|forex|overseas|remittance|external commercial|\becb\b|government securities|treasury",
}
# Terms relevant to EVERY regulated profile.
_UNIVERSAL = r"master direction|kyc|know your customer|anti.?money|aml|fraud|ombudsman|fair practice"

_SEVERITY_RULES = [
    ("amendment", r"amendment|amended|revised|modification|review of|withdrawal", "Rule CHANGED — check affected memories/policies"),
    ("new_direction", r"master direction|directions, 20\d\d|framework|guidelines", "New/updated framework"),
    ("enforcement", r"penalty|penalties|monetary penalty|enforcement|cancell", "Enforcement signal — conduct risk radar"),
    ("draft", r"draft|comments|consultation", "Upcoming — comment window open"),
]


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def _parse(xml_text: str, kind: str) -> list[dict]:
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # RBI feeds occasionally embed stray ampersands; degrade gracefully.
        xml_text = re.sub(r"&(?!amp;|lt;|gt;|quot;|#)", "&amp;", xml_text)
        root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        if title:
            items.append({"kind": kind, "title": title, "link": link, "date": pub})
    return items


def classify(title: str) -> dict:
    """Map a circular title to affected profiles + severity, explainably."""
    tl = title.lower()
    profiles, matched = [], []
    for prof, pat in PROFILES.items():
        m = re.findall(pat, tl)
        if m:
            profiles.append(prof)
            matched += sorted(set(m))[:3]
    if re.search(_UNIVERSAL, tl):
        if not profiles:
            profiles = list(PROFILES)  # universal obligations hit everyone
        matched += sorted(set(re.findall(_UNIVERSAL, tl)))[:2]
    severity, note = "info", "Informational"
    for sev, pat, msg in _SEVERITY_RULES:
        if re.search(pat, tl):
            severity, note = sev, msg
            break
    return {"profiles": profiles, "matched": sorted(set(matched)), "severity": severity, "note": note}


def _load_state() -> dict:
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"seen": []}


def _save_state(state: dict) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, indent=0), encoding="utf-8")


# Fetch-cache: RBI throttles rapid repeat hits; page loads must not re-fetch.
_CACHE: dict = {"at": 0.0, "items": None}
_CACHE_TTL = 600  # seconds


def _all_items() -> list[dict]:
    import time as _t

    if _CACHE["items"] is not None and _t.time() - _CACHE["at"] < _CACHE_TTL:
        return _CACHE["items"]
    items = []
    for kind, url in FEEDS.items():
        try:
            items += _parse(_fetch(url), kind)
        except Exception as e:  # noqa: BLE001 - one dead feed must not kill the check
            items.append({"kind": kind, "title": f"(feed unavailable: {e})",
                          "link": "", "date": ""})
    if any(i["link"] for i in items):  # only cache a run that actually fetched
        _CACHE.update(at=_t.time(), items=items)
    return items


def check(profile: str = "", limit: int = 40) -> dict:
    """Classify feed items for a profile, mark which are NEW since last check.

    Returns {"alerts": [...], "new_count": int, "checked_at": iso}.
    """
    state = _load_state()
    seen = set(state.get("seen", []))
    alerts, new_ids = [], []
    for item in _all_items():
        uid = item["link"] or item["title"]
        c = classify(item["title"])
        if profile and profile != "all" and profile not in c["profiles"]:
            continue
        is_new = uid not in seen and bool(item["link"])
        if is_new:
            new_ids.append(uid)
        alerts.append({**item, **c, "new": is_new})
    state["seen"] = list(seen | set(new_ids))[-5000:]
    _save_state(state)
    # amendments & new directions first, then the rest, feed order within rank
    rank = {"amendment": 0, "new_direction": 1, "enforcement": 2, "draft": 3, "info": 4}
    alerts.sort(key=lambda a: rank.get(a["severity"], 9))
    return {"alerts": alerts[:limit], "new_count": len(new_ids),
            "checked_at": datetime.now(timezone.utc).isoformat()}
