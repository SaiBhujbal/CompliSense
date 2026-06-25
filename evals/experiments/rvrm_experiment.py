"""
RVRM (Reconstruction-Verified Residual Memory) — real test with gemma-4-31b-it.

Novel claim under test: a span should be dropped from context ONLY IF the model
can regenerate its CORRECT value from the rest (reconstruction-verified), NOT
merely because the model is confident about it (predictability-based, a la
Selective Context / LLMLingua). The two diverge on CONFIDENTLY-WRONG facts
(stale parametric belief): predictability-drop discards them -> stale wrong
answer; RVRM detects reconstruction != source -> KEEPS them -> correct answer.

Conditions per item (Gemma answers the question from the resulting context):
  FULL            : keep the fact (upper bound)
  PREDICT-DROP    : drop the fact if the model confidently predicts a value
                    (LLMLingua-spirit: predictable -> drop)
  RVRM            : drop the fact only if the model's reconstruction MATCHES the
                    true value; else keep (lossless-relative-to-model)

Metric: answer accuracy per condition, split by fact category
(confidently-wrong / confidently-right / unknown) + #facts kept.
Pure Google API (no torch). Reads GOOGLE_API_KEY from .env (gitignored).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

MODEL = "models/gemma-4-31b-it"

# category: cw=confidently-wrong (stale/counterfactual updated value),
# cr=confidently-right (true & well-known), un=unknown (obscure/arbitrary)
ITEMS = [
    # confidently-wrong: passage states an UPDATED/counterfactual value the model likely won't predict
    ("Per the 2026 revision, the co-lending minimum retention was changed to {V}.", "7 percent",
     "What is the co-lending minimum retention per the 2026 revision?", "cw"),
    ("Effective this year, the NBFC-ICC minimum net owned fund was set to {V}.", "13 crore",
     "What is the NBFC-ICC minimum net owned fund effective this year?", "cw"),
    ("Under the amended rule, the single-borrower P2P cap is now {V}.", "65,000",
     "What is the amended single-borrower P2P cap?", "cw"),
    ("The revised DLG ceiling in co-lending was lowered to {V}.", "4 percent",
     "What is the revised DLG ceiling in co-lending?", "cw"),
    ("As newly notified, the digital-loan cooling-off period is {V}.", "9 days",
     "What is the newly notified digital-loan cooling-off period?", "cw"),
    ("The latest circular sets the co-lending transfer window at {V}.", "12 calendar days",
     "What is the co-lending transfer window in the latest circular?", "cw"),
    # confidently-right: true, well-known stable facts (model should reconstruct correctly)
    ("Water boils at {V} at sea level.", "100 degrees Celsius",
     "At what temperature does water boil at sea level?", "cr"),
    ("A right angle measures {V}.", "90 degrees",
     "How many degrees is a right angle?", "cr"),
    ("India gained independence in {V}.", "1947",
     "In which year did India gain independence?", "cr"),
    # unknown: obscure/arbitrary facts the model cannot know (must keep)
    ("The internal audit reference code for this filing is {V}.", "QX-7741",
     "What is the internal audit reference code for this filing?", "un"),
    ("The pilot cohort enrolled exactly {V} participants.", "382",
     "How many participants did the pilot cohort enroll?", "un"),
    ("The committee met on {V} to finalize the note.", "the third Tuesday of March",
     "On what day did the committee meet to finalize the note?", "un"),
]
PREDICTABLE = "This document outlines applicable obligations for regulated entities in the sector."


def gemma(prompt, key, max_tok=60, retries=4):
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.0, "maxOutputTokens": max_tok}}).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503):
                time.sleep(3 * (a + 1)); continue
            return f"[HTTP {e.code}]"
        except Exception:
            time.sleep(2)
    return "[ERR]"


import re as _re


def judge(question, true_val, candidate, key=None):
    """Robust code-based value match (gemma-4 won't emit clean YES/NO verdicts).
    Normalize away spacing/commas and percent wording, then substring-check."""
    def nrm(s):
        s = s.lower().replace("per cent", "%").replace("percent", "%")
        return _re.sub(r"[,\s]+", "", s)
    return nrm(true_val) in nrm(candidate)


def main():
    key = next(l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("GOOGLE_API_KEY="))
    cats = ["cw", "cr", "un"]
    acc = {c: {"FULL": [0, 0], "PREDICT-DROP": [0, 0], "RVRM": [0, 0]} for c in cats}
    kept = {"PREDICT-DROP": 0, "RVRM": 0}
    n = len(ITEMS)
    print(f"Model {MODEL} | {n} items | LLM-as-judge\n", flush=True)

    for tmpl, val, q, cat in ITEMS:
        fact = tmpl.format(V=val)
        full_ctx = f"{PREDICTABLE} {fact}"
        masked = f"{PREDICTABLE} " + tmpl.format(V="_____")

        # PREDICT-DROP decision: does the model confidently produce a value w/o context?
        pred = gemma(f"Question: {q}\nState the value, or say UNKNOWN if you are unsure.", key, 96)
        _pl = pred.lower()
        _unsure = any(u in _pl for u in ["unknown", "don't know", "do not know", "cannot", "unable", "not able", "no information", "not sure"])
        predictable = not _unsure and not pred.startswith("[")
        pdrop_ctx = PREDICTABLE if predictable else full_ctx
        if not predictable:
            kept["PREDICT-DROP"] += 1

        # RVRM decision: can the model RECONSTRUCT the CORRECT value (judged) from the rest?
        recon = gemma(f"Fill the blank with the correct value.\n{masked}\nBlank value:", key, 96)
        reconstructable = judge(q, val, recon, key)
        rvrm_ctx = PREDICTABLE if reconstructable else full_ctx  # drop only if correctly reconstructable
        if not reconstructable:
            kept["RVRM"] += 1

        ap = "Answer using ONLY the context. If absent, reply UNKNOWN.\nContext: {c}\nQ: {q}\nA:"
        for cond, ctx in [("FULL", full_ctx), ("PREDICT-DROP", pdrop_ctx), ("RVRM", rvrm_ctx)]:
            ans = gemma(ap.format(c=ctx, q=q), key, 256)
            ok = judge(q, val, ans, key)
            acc[cat][cond][0] += ok
            acc[cat][cond][1] += 1
            time.sleep(0.3)

    print(f"{'category':<20}{'FULL':>10}{'PREDICT-DROP':>16}{'RVRM':>10}")
    for c in cats:
        name = {"cw": "confidently-wrong", "cr": "confidently-right", "un": "unknown"}[c]
        row = f"{name:<20}"
        for cond in ["FULL", "PREDICT-DROP", "RVRM"]:
            h, t = acc[c][cond]
            row += f"{(h/t if t else 0):>9.0%} " if cond != "FULL" else f"{(h/t if t else 0):>9.0%} "
        print(row, flush=True)
    # overall
    print("-" * 56)
    for cond in ["FULL", "PREDICT-DROP", "RVRM"]:
        h = sum(acc[c][cond][0] for c in cats); t = sum(acc[c][cond][1] for c in cats)
        print(f"  {cond:<14} overall accuracy {h}/{t} = {h/t:.0%}", flush=True)
    print(f"\n  facts kept (lower=more compression): PREDICT-DROP={kept['PREDICT-DROP']}/{n}, RVRM={kept['RVRM']}/{n}")
    print("  (RVRM should match FULL accuracy, esp. on confidently-wrong, while keeping few facts)")


if __name__ == "__main__":
    main()
