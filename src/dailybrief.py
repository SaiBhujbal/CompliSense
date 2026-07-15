"""Daily Brief — evidence-hashed PESTEL/SWOT monitoring (the trust engine).

The owner's requirement, made structural:
  1. DAILY monitoring — the market read is recomputed from the Watchtower feed.
  2. STABILITY — the brief is keyed to an EVIDENCE HASH (sha256 of the sorted
     alert ids). Same evidence => the STORED brief is returned byte-identical.
     Ask today, ask next week: the answer cannot drift unless the market did.
  3. PROVENANCE — every delta carries the circular that caused it. No delta
     exists without a source. v1 is fully DETERMINISTIC (rule-mapped from the
     Watchtower classification): explainable, free, reproducible. An LLM
     enrichment layer can be added ON TOP later without touching the guarantees.

Pure stdlib — safe to import in server.py.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .watchtower import check

_STORE = Path(__file__).parent.parent / "data" / "daily_brief.json"

# Watchtower profile -> which PESTEL force an event moves, and how.
_FORCE_MAP = {
    "lending": ("Legal", "tightening"),
    "payments": ("Legal", "tightening"),
    "p2p": ("Legal", "tightening"),
    "aa_data": ("Technological", "shifting"),
    "markets_fx": ("Economic", "moving"),
}
_SEV_TO_SWOT = {
    # severity -> (SWOT quadrant, framing)
    "amendment": ("Threats", "A rule you may rely on just changed"),
    "new_direction": ("Threats", "New framework raises the compliance floor"),
    "enforcement": ("Threats", "Enforcement signal — conduct risk is live"),
    "draft": ("Opportunities", "Comment window open — early-mover shaping chance"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    try:
        return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(d: dict) -> None:
    _STORE.parent.mkdir(parents=True, exist_ok=True)
    _STORE.write_text(json.dumps(d, indent=1), encoding="utf-8")


def _evidence_hash(alerts: list[dict]) -> str:
    ids = sorted(a.get("link", "") for a in alerts if a.get("link"))
    return hashlib.sha256("|".join(ids).encode()).hexdigest()[:16]


def _build(alerts: list[dict]) -> dict:
    """Deterministic brief from classified alerts — every item cites its circular."""
    forces: dict = {}
    swot: dict = {"Threats": [], "Opportunities": []}
    for a in alerts:
        if not a.get("link"):
            continue
        sev = a.get("severity", "info")
        for prof in a.get("profiles", []):
            if prof in _FORCE_MAP and sev in ("amendment", "new_direction", "enforcement"):
                force, direction = _FORCE_MAP[prof]
                f = forces.setdefault(force, {"direction": direction, "events": []})
                if len(f["events"]) < 5:
                    f["events"].append({"title": a["title"], "link": a["link"],
                                        "severity": sev, "date": a.get("date", "")})
        if sev in _SEV_TO_SWOT:
            quad, why = _SEV_TO_SWOT[sev]
            if len(swot[quad]) < 6:
                swot[quad].append({"title": a["title"], "link": a["link"],
                                   "why": why, "profiles": a.get("profiles", [])})
    return {"pestel_forces": forces, "swot_updates": swot}


def get_brief(force_refresh: bool = False) -> dict:
    """Return today's brief. STABLE: recomputed only when the evidence changes."""
    stored = _load()
    res = check(profile="all", limit=60)
    alerts = [a for a in res.get("alerts", []) if a.get("link")]
    h = _evidence_hash(alerts)

    if not force_refresh and stored.get("evidence_hash") == h and stored.get("brief"):
        # Evidence unchanged -> the read is unchanged. This is the trust guarantee.
        stored["stable"] = True
        stored["checked_at"] = _now()
        _save(stored)
        return stored

    prev_hash = stored.get("evidence_hash")
    brief = _build(alerts)
    # what's NEW versus the previous evidence set (the "sudden change" pointer)
    prev_ids = set(stored.get("alert_ids", []))
    new_alerts = [{"title": a["title"], "link": a["link"], "severity": a["severity"],
                   "profiles": a["profiles"]}
                  for a in alerts if a["link"] not in prev_ids][:10]
    out = {
        "evidence_hash": h,
        "previous_hash": prev_hash,
        "since": stored.get("since") or _now(),   # when this evidence era began
        "updated_at": _now(),
        "checked_at": _now(),
        "stable": False,
        "alert_ids": [a["link"] for a in alerts],
        "new_since_last": new_alerts,
        "brief": brief,
        "method": ("Deterministic rule-mapping from RBI official feeds "
                   "(rbi.org.in). Every delta cites its circular. Identical "
                   "evidence always yields the identical brief."),
    }
    if prev_hash != h:
        out["since"] = _now()
    _save(out)
    return out
