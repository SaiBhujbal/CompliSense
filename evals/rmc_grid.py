"""RMC step 3 — pre-registered LLM grid on Groq (qwen3.6-27b).

Hypotheses FIXED in research/REGULATORY_MEMORY_CONSOLIDATION.md BEFORE this run:
  H1: RMC >= full-context RAG on normative recall at <=40% of its tokens/query.
  H2: generic (normativity-blind) compression loses >=15pp verbatim normative
      recall vs RMC at equal budget.
  H3: after amendments, non-AAI memories answer >=30% of affected queries stale;
      AAI cuts staleness to <5%.
  KILL: if the tiered-no-VSI ablation matches RMC within 2pp at equal budget,
      the mechanism contribution collapses to the benchmark alone.

Systems (same LLM answers; only the CONTEXT differs):
  FULL     entire ingested chunk set, re-read per query (lossless, expensive;
           post-amendment it reads the AMENDED corpus -> fresh by construction).
  GENERIC  normativity-blind flat compression to ~RMC's budget (position-based
           LLMLingua-class STAND-IN — real LLMLingua-2 is future work), no AAI.
  TIERED   dormant-tier + cue recovery + provenance but NO VSI, NO AAI
           (the prior-art ablation / kill-criterion baseline).
  RMC      full: VSI + CGW + AAI ("meditation" scheduler).

Honest limits: n=9 questions / 6 amendments -> NO significance claims; GENERIC
is a stand-in, not LLMLingua-2; single model, single seed. Run:
  python -m evals.rmc_grid
"""

import src._bootstrap  # noqa: F401

import json
import os
import random
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from evals.normbench_ground import variants
from src.memory.rmc import RMCMemory
from src.rag.compression import _approx_tokens, _split

load_dotenv()

_HERE = Path(__file__).parent
_GROUND = _HERE / "dataset" / "normbench_grounding.json"
_AMEND = _HERE / "dataset" / "normbench_amendments.jsonl"
_BENCH = _HERE / "dataset" / "rbi_normbench.jsonl"
_OUT = _HERE / "dataset" / "rmc_grid_results.json"

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

PROMPT = ("You are a precise RBI compliance analyst. Answer ONLY from the context. "
          "State exact thresholds, percentages and dates VERBATIM as written in the "
          "context. If the context lacks the answer, say 'not in context'. /no_think\n\n"
          "Context:\n{ctx}\n\nQuestion: {q}\n\nAnswer:")


# Groq free tier: qwen3.6-27b TPM = 8000 (input+output, rolling minute). Pace at
# an EFFECTIVE 6000/min (25% headroom — run 2 proved zero-headroom pacing still
# collides with the rolling window); on 429, wait a FULL window before retrying.
_TPM_EFFECTIVE = 6000
_MAX_OUT = 700


def _pace(ctx_tokens: int) -> None:
    time.sleep(max(8, int(60 * (ctx_tokens + _MAX_OUT + 120) / _TPM_EFFECTIVE)))


def llm_call(llm, ctx: str, q: str, tries: int = 3) -> str | None:
    """Returns the answer text, or None if the call ultimately FAILED —
    callers must treat None as missing data, never as a wrong answer."""
    for attempt in range(tries):
        try:
            r = llm.invoke(PROMPT.format(ctx=ctx, q=q))
            return _THINK_RE.sub("", r.content or "").strip()
        except Exception as e:  # noqa: BLE001 - rate limits etc.
            if attempt == 0:
                print(f"    [err: {str(e)[:140]}]", flush=True)
            time.sleep(70)  # full TPM window reset
    return None


def fact_in(fact: str, text: str) -> bool:
    tl = text.lower()
    return any(v in tl for v in variants(fact))


# ----------------------------------------------------------------------- #
class GenericMemory:
    """Position-based flat compression to ~budget_ratio of each chunk. No tiers,
    no recovery, no AAI."""

    def __init__(self, ratio: float) -> None:
        self.ratio = ratio
        self.gists: list[str] = []

    def build(self, chunks) -> None:
        for text, _, _ in chunks:
            sents = _split(text)
            keep = max(1, int(len(sents) * self.ratio))
            self.gists.append(" ".join(sents[:keep]))

    def context(self, cue: str = "") -> str:
        return " ".join(self.gists)

    def standing_tokens(self) -> int:
        return sum(_approx_tokens(g) for g in self.gists)


class TieredNoVSI:
    """Ablation: tiered memory with keyword cue-recovery and provenance but the
    gist is position-based (normativity-blind) and there is NO AAI."""

    def __init__(self, ratio: float) -> None:
        self.ratio = ratio
        self.gists: list[str] = []
        self.dormant: list[str] = []

    def build(self, chunks) -> None:
        for text, _, _ in chunks:
            sents = _split(text)
            keep = max(1, int(len(sents) * self.ratio))
            self.gists.append(" ".join(sents[:keep]))
            self.dormant += sents[keep:]

    def context(self, cue: str = "") -> str:
        from src.memory.dtcam import _keywords
        parts = list(self.gists)
        if cue:
            ck = _keywords(cue)
            parts += [d for d in self.dormant if ck & _keywords(d)]
        return " ".join(parts)

    def standing_tokens(self) -> int:
        return sum(_approx_tokens(g) for g in self.gists)


def _ci_replace(text: str, old: str, new: str) -> str:
    return re.sub(re.escape(old), new, text, flags=re.IGNORECASE)


# ----------------------------------------------------------------------- #
def main() -> int:
    from langchain_openai import ChatOpenAI

    from src.rag.retriever import _all_documents

    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("GROQ_API_KEY missing in .env", file=sys.stderr)
        return 1
    llm = ChatOpenAI(api_key=key, base_url="https://api.groq.com/openai/v1",
                     model=os.getenv("GROQ_REASONING_MODEL", "qwen/qwen3.6-27b"),
                     temperature=0, max_tokens=_MAX_OUT)

    docs = _all_documents()
    grounding = json.loads(_GROUND.read_text(encoding="utf-8"))
    amendments = [json.loads(l) for l in _AMEND.read_text(encoding="utf-8").splitlines() if l.strip()]
    bench = {json.loads(l)["id"]: json.loads(l)
             for l in _BENCH.read_text(encoding="utf-8").splitlines() if l.strip()}

    lookup: dict = {}
    for d in docs:
        k = (d.metadata.get("source", "?"), d.metadata.get("page", "?"))
        lookup[k] = (lookup.get(k, "") + "\n" + d.page_content).strip()

    # Grounded items: question + expected key facts (only grounded obligations).
    items, pages = [], set()
    for item_id, obs in grounding.items():
        if not isinstance(obs, dict) or "status" in obs:
            continue
        gfacts = []
        for r in obs.values():
            if r.get("status") == "grounded":
                pages.add((r["source"], r["page"]))
                gfacts += list(r["matched"].keys())
        if gfacts:
            items.append({"id": item_id, "q": bench[item_id]["question"], "facts": gfacts})
    print(f"Grid: {len(items)} grounded questions, {len(amendments)} amendments")

    rng = random.Random(7)
    chunks = [(lookup[p], p[0], p[1]) for p in sorted(pages, key=str)]
    raw_tokens = sum(_approx_tokens(t) for t, _, _ in chunks)
    # Distractors up to a raw budget that keeps FULL's context + output under the
    # Groq 8000-TPM window (grounded pages are mandatory; distractors fill the rest).
    _RAW_BUDGET = 5200
    others = [d for d in docs if (d.metadata.get("source"), d.metadata.get("page")) not in pages]
    rng.shuffle(others)
    for d in others:
        t = _approx_tokens(d.page_content)
        if raw_tokens + t > _RAW_BUDGET:
            continue
        chunks.append((d.page_content, d.metadata.get("source", "?"), d.metadata.get("page", "?")))
        raw_tokens += t

    # Build systems; match GENERIC/TIERED budget to RMC's realized ratio.
    rmc = RMCMemory()
    rmc.ingest(list(chunks))
    rmc.meditate(lookup)
    ratio = rmc.standing_tokens() / raw_tokens
    gen = GenericMemory(ratio); gen.build(chunks)
    tier = TieredNoVSI(ratio); tier.build(chunks)
    full_ctx = " ".join(t for t, _, _ in chunks)
    print(f"budgets: raw={raw_tokens} RMC={rmc.standing_tokens()} "
          f"GENERIC={gen.standing_tokens()} TIERED={tier.standing_tokens()} (ratio {ratio:.2f})")

    systems = {"FULL": lambda q: full_ctx, "GENERIC": gen.context,
               "TIERED": tier.context, "RMC": rmc.context}
    # RESUMABLE: reload prior partial results; skip completed systems so a
    # timeout/kill never wastes the API budget already spent.
    results = {"phaseA": {}, "phaseB": {}, "budgets": {
        "raw": raw_tokens, "RMC": rmc.standing_tokens(),
        "GENERIC": gen.standing_tokens(), "TIERED": tier.standing_tokens()}}
    if _OUT.exists():
        try:
            prev = json.loads(_OUT.read_text(encoding="utf-8"))
            for ph in ("phaseA", "phaseB"):
                for k, v in (prev.get(ph) or {}).items():
                    if v.get("failed") == 0:  # explicit clean run only
                        results[ph][k] = v
            if results["phaseA"] or results["phaseB"]:
                print(f"[resume] reusing clean results: "
                      f"A={list(results['phaseA'])} B={list(results['phaseB'])}")
        except Exception:  # noqa: BLE001
            pass

    def _save():
        _OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # ---------------- Phase A: normative recall in ANSWERS ---------------- #
    print("\n== Phase A: answer-level normative recall (pre-amendment) ==")
    for name, ctx_fn in systems.items():
        if name in results["phaseA"]:
            a = results["phaseA"][name]
            print(f"  {name:8s} recall={a['recall']:.0%} (resumed)")
            continue
        hits = total = toks = failed = 0
        for it in items:
            ctx = ctx_fn(it["q"])
            ct = _approx_tokens(ctx)
            toks += ct
            ans = llm_call(llm, ctx, it["q"])
            if ans is None:
                failed += 1            # missing data — NOT scored as wrong
            else:
                for f in it["facts"]:
                    total += 1
                    hits += fact_in(f, ans)
            _pace(ct)
        recall = hits / total if total else 0.0
        results["phaseA"][name] = {"recall": recall, "mean_tokens": toks // len(items),
                                   "answered": len(items) - failed, "failed": failed}
        _save()
        print(f"  {name:8s} recall={recall:.0%} (over {len(items)-failed}/{len(items)} answered)"
              f"  mean input tokens/query={toks//len(items)}")

    # ---------------- Phase B: amendment staleness ------------------------ #
    amended_lookup = dict(lookup)
    for a in amendments:
        for k in list(amended_lookup):
            if k[0] == a["source"]:
                amended_lookup[k] = _ci_replace(amended_lookup[k], a["surface_old"], a["surface_new"])
    for a in amendments:
        rmc.apply_amendment(a["source"], a["surface_old"], a["surface_new"], amended_lookup)
    rmc.meditate(amended_lookup)
    full_amended = " ".join(amended_lookup.get((s, p), t) for t, s, p in chunks)

    by_item: dict = {}
    for a in amendments:
        by_item.setdefault(a["item_id"], []).append(a)
    systemsB = {"FULL": lambda q: full_amended, "GENERIC": gen.context,
                "TIERED": tier.context, "RMC": rmc.context}

    print("\n== Phase B: post-amendment freshness (fresh = NEW value in answer) ==")
    for name, ctx_fn in systemsB.items():
        if name in results["phaseB"]:
            b = results["phaseB"][name]
            print(f"  {name:8s} fresh={b['fresh']:.0%}  stale={b['stale']:.0%} (resumed)")
            continue
        fresh = stale = total = failed = 0
        for item_id, ams in by_item.items():
            if item_id not in bench:
                continue
            ctx = ctx_fn(bench[item_id]["question"])
            ans = llm_call(llm, ctx, bench[item_id]["question"])
            if ans is None:
                failed += 1            # missing data — NOT scored
            else:
                for a in ams:
                    total += 1
                    if fact_in(a["fact_new"], ans):
                        fresh += 1
                    elif fact_in(a["fact_old"], ans):
                        stale += 1
            _pace(_approx_tokens(ctx))
        fr = fresh / total if total else 0.0
        st = stale / total if total else 0.0
        results["phaseB"][name] = {"fresh": fr, "stale": st, "n": total, "failed": failed}
        _save()
        print(f"  {name:8s} fresh={fr:.0%}  stale={st:.0%}  (n={total}, failed calls={failed})")

    # ---------------- Verdicts (pre-registered) --------------------------- #
    A, B = results["phaseA"], results["phaseB"]
    invalid = (any(v["failed"] for v in A.values()) or any(v["failed"] for v in B.values()))
    if invalid:
        print("\n!! RUN INVALID for hypothesis testing: some calls failed (rate limits). "
              "Numbers below are coverage-limited — do NOT cite as H-verdicts.")
    results["valid"] = not invalid
    h1 = (A["RMC"]["recall"] >= A["FULL"]["recall"]
          and A["RMC"]["mean_tokens"] <= 0.40 * A["FULL"]["mean_tokens"])
    h2 = (A["RMC"]["recall"] - A["GENERIC"]["recall"]) >= 0.15
    h3 = (B["TIERED"]["stale"] >= 0.30 and B["RMC"]["stale"] < 0.05)
    kill = abs(A["RMC"]["recall"] - A["TIERED"]["recall"]) <= 0.02
    print(f"\nH1 (recall>=FULL at <=40% tokens): {'PASS' if h1 else 'FAIL'}")
    print(f"H2 (>=15pp over generic):          {'PASS' if h2 else 'FAIL'}")
    print(f"H3 (staleness >=30% -> <5%):       {'PASS' if h3 else 'FAIL'}")
    print(f"KILL criterion (TIERED within 2pp): {'TRIGGERED' if kill else 'not triggered'}")
    results["verdicts"] = {"H1": h1, "H2": h2, "H3": h3, "kill": kill}
    _OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {_OUT.name}. Caveats: n={len(items)} questions/{len(amendments)} "
          "amendments (no significance), GENERIC is an LLMLingua STAND-IN, single model/seed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
