"""NormBench corpus-grounding check + amendment simulator (zero API cost).

Step 1 of the RMC research plan (research/REGULATORY_MEMORY_CONSOLIDATION.md):

1. GROUNDING: for every 'answer' item in rbi_normbench.jsonl, verify each
   obligation's key_facts appear VERBATIM (surface-form variants allowed) in the
   ingested corpus — all facts of an obligation must co-occur in ONE chunk.
   Items that were web-verified but do not ground in OUR corpus are flagged:
   they cannot score a retrieval system and must not count.
2. AMENDMENTS: for grounded NUMERIC/DATE facts, generate simulated amendments
   (threshold/date changed) with the exact matched surface so the AAI eval can
   materialize an amended corpus and measure staleness errors.

Run:  python -m evals.normbench_ground        (writes dataset/normbench_grounding.json
                                               + dataset/normbench_amendments.jsonl)
"""

import src._bootstrap  # noqa: F401  -- torch before chromadb (segfault guard)

import json
import re
import sys
from pathlib import Path

from evals.schema import BenchItem

_HERE = Path(__file__).parent
_DATASET = _HERE / "dataset" / "rbi_normbench.jsonl"
_OUT_GROUND = _HERE / "dataset" / "normbench_grounding.json"
_OUT_AMEND = _HERE / "dataset" / "normbench_amendments.jsonl"


# --------------------------------------------------------------------------- #
# Surface-form variants: RBI documents write "26 per cent", "Rs.10 crore", etc.
# --------------------------------------------------------------------------- #
def variants(fact: str) -> list[str]:
    f = fact.strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%", f)
    if m:
        n = m.group(1)
        return [f"{n}%", f"{n} %", f"{n} per cent", f"{n} percent", f"{n} per cent."]
    m = re.fullmatch(r"(\d+(?:,\d+)*)\s*(crore|lakh|cr)", f)
    if m:
        n, unit = m.group(1), m.group(2)
        unit_forms = ["crore", "cr"] if unit in ("crore", "cr") else ["lakh", "lac"]
        out = []
        for u in unit_forms:
            out += [f"{n} {u}", f"rs {n} {u}", f"rs.{n} {u}", f"₹{n} {u}", f"rs. {n} {u}"]
        return out
    if re.fullmatch(r"\d{4}", f):  # year
        return [f]
    if re.fullmatch(r"\d+(,\d+)*", f):  # bare number (e.g. "50,000", "15")
        return [f]
    return [f]  # plain keyword ("cooling", "apr", "pass-through", ...)


def find_in_chunk(text_lower: str, fact: str) -> str | None:
    """Return the variant that occurs in the chunk, else None."""
    for v in variants(fact):
        if v in text_lower:
            return v
    return None


# --------------------------------------------------------------------------- #
# Topic guard: a number appearing SOMEWHERE in the corpus is not grounding —
# "10%" for co-lending retention must not match KYC's 10% beneficial-ownership
# threshold. The chunk must ALSO contain a topic term of the obligation.
# --------------------------------------------------------------------------- #
_TOPIC_TERMS = {
    "change_of_control": ["shareholding", "change in management", "transfer of control",
                          "acquisition", "change in control"],
    "digital_lending": ["digital lending", "lending service provider", "default loss guarantee",
                        "dlg", "key fact", "cooling", "borrower"],
    "p2p_lending": ["peer to peer", "peer-to-peer", "p2p"],
    "scale_based_regulation": ["net owned fund", "nof", "owned fund"],
    "co_lending": ["co-lending", "co lending", "colending"],
    "priority_sector_lending": ["priority sector"],
}


# --------------------------------------------------------------------------- #
# Amendment rules — only numeric/date facts are amendable.
# --------------------------------------------------------------------------- #
def amended_value(fact: str) -> str | None:
    f = fact.strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%", f)
    if m:
        return f"{int(float(m.group(1))) + 3}%"
    m = re.fullmatch(r"(\d+)\s*(crore|lakh|cr)", f)
    if m:
        return f"{int(m.group(1)) + 2} {m.group(2)}"
    if re.fullmatch(r"\d{4}", f):
        return str(int(f) + 2)
    m = re.fullmatch(r"(\d+),000", f)
    if m:
        return f"{int(m.group(1)) + 25},000"
    return None  # keywords / bare small ints: not amendable


def main() -> int:
    from src.rag.retriever import _all_documents

    docs = _all_documents()
    if not docs:
        print("ERROR: corpus is empty — run ingest_data.py first.", file=sys.stderr)
        return 1
    lowered = [(d.page_content.lower(), d) for d in docs]
    print(f"Corpus: {len(docs)} chunks loaded.\n")

    items = [BenchItem.from_dict(json.loads(line))
             for line in _DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]

    grounding: dict = {}
    amendments: list[dict] = []
    n_ob, n_grounded = 0, 0

    for item in items:
        if item.expected_behavior != "answer":
            grounding[item.id] = {"status": "n/a (abstain item)"}
            continue
        ob_results = {}
        for ob in item.required_obligations:
            if not ob.key_facts:
                ob_results[ob.id] = {"status": "unlabelled (expert label required)"}
                continue
            n_ob += 1
            # Grounded iff ONE chunk contains ALL key_facts (variant-matched)
            # AND at least one topic term of the item's category (anti-spurious).
            topics = _TOPIC_TERMS.get(item.category, [])
            hit = None
            for text_lower, doc in lowered:
                if topics and not any(t in text_lower for t in topics):
                    continue
                matched = {f: find_in_chunk(text_lower, f) for f in ob.key_facts}
                if all(matched.values()):
                    hit = (doc, matched)
                    break
            if hit is None:
                ob_results[ob.id] = {"status": "UNGROUNDED", "facts": ob.key_facts}
                continue
            doc, matched = hit
            n_grounded += 1
            src = doc.metadata.get("source", "?")
            page = doc.metadata.get("page", "?")
            ob_results[ob.id] = {"status": "grounded", "source": src, "page": page,
                                 "matched": matched}
            # Amendment candidates from the grounded facts.
            for fact, surface in matched.items():
                new = amended_value(fact)
                if new is None:
                    continue
                n_aff = sum(1 for tl, _ in lowered if surface in tl)
                # Amended surface = same wording, new number ("26 per cent"->"29 per cent").
                old_num = re.search(r"\d+(?:,\d+)*(?:\.\d+)?", surface).group(0)
                new_num = re.search(r"\d+(?:,\d+)*(?:\.\d+)?", new).group(0)
                amendments.append({
                    "item_id": item.id, "obligation_id": ob.id,
                    "fact_old": fact, "fact_new": new,
                    "surface_old": surface,
                    "surface_new": surface.replace(old_num, new_num),
                    "source": src, "page": page, "chunks_affected": n_aff,
                })
        grounding[item.id] = ob_results

    _OUT_GROUND.write_text(json.dumps(grounding, indent=2), encoding="utf-8")
    with _OUT_AMEND.open("w", encoding="utf-8") as f:
        for a in amendments:
            f.write(json.dumps(a) + "\n")

    print(f"Obligations checked: {n_ob} | grounded in corpus: {n_grounded} "
          f"| UNGROUNDED: {n_ob - n_grounded}")
    print(f"Amendments generated: {len(amendments)}\n")
    for item_id, obs in grounding.items():
        if isinstance(obs, dict) and "status" in obs:
            continue
        for ob_id, r in obs.items():
            flag = "OK " if r.get("status") == "grounded" else "!! "
            extra = f"{r.get('source', '')} p.{r.get('page', '')}" if r.get("status") == "grounded" else r.get("status")
            print(f"{flag}{item_id}/{ob_id}: {extra}")
    print(f"\nWrote {_OUT_GROUND.name} and {_OUT_AMEND.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
