"""
REAL end-to-end experiment with Gemma-4-31b-it answering (Google API).

Goes beyond retrieval-recall: for each memory/RAG system we assemble context,
then a REAL LLM answers the cue query from that context, and we score whether
the answer states the correct conditional nuance. HARD setting: distractors are
semantically SIMILAR to targets (same topic, no carve-out), so dense retrieval
pulls them in and DILUTES context. Hypothesis: DT-CAM's clean conditional-span
context yields better LLM answers than VanillaRAG's full-doc (diluted) context,
even when both technically contain the nuance.

Reads GOOGLE_API_KEY from .env (gitignored). No key is printed.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import numpy as np

BUDGET = 900
N_DISTRACT = 60
MODEL = "models/gemma-4-31b-it"

# (main, conditional-nuance, cue-query, gold_key that a CORRECT answer must contain)
ITEMS = [
    ("Each co-lender must retain at least 10 percent of every loan",
     "but the originating lender may also provide a default loss guarantee of up to 5 percent as an optional extra",
     "Besides the mandatory retention, can the originator add any optional extra credit support, and how much?",
     "5 percent"),
    ("A single borrower's exposure is capped at Rs 50,000 across P2P platforms",
     "but a lender deploying more than Rs 10 lakh must additionally furnish a net worth certificate",
     "If a P2P lender deploys more than 10 lakh in total, is anything additional required of them?",
     "net worth certificate"),
    ("Loan disbursals must normally go directly to the borrower's bank account",
     "except in co-lending between regulated entities or specific mandated end-use, where alternate routing is allowed",
     "Are there any exceptions where a loan need not be disbursed directly to the borrower?",
     "co-lending"),
    ("The board must approve the compliance policy every year",
     "however the board may delegate operational approvals to a committee where workload requires",
     "Must the board personally handle all operational approvals, or is there flexibility?",
     "committee"),
    ("Entities shall file the quarterly return by the stipulated date",
     "though smaller entities below the turnover threshold may optionally adopt a simplified format",
     "Do smaller entities below the threshold have any easier filing option?",
     "simplified"),
    ("Digital lending apps must store customer data on servers located in India",
     "but aggregated anonymised data may be processed abroad for analytics where contractually permitted",
     "Is there any case where digital-lending customer data may be processed outside India?",
     "anonymised"),
    ("NBFCs must obtain prior RBI approval for a change in control",
     "except where the shareholding increase results solely from a court-approved buyback, which is only reported",
     "Is prior RBI approval ever NOT needed when shareholding crosses the control threshold?",
     "buyback"),
    ("KYC must be completed before onboarding a lending customer",
     "but video-based customer identification is permitted as an alternative to in-person KYC",
     "Is in-person KYC the only option, or is there a permitted alternative?",
     "video"),
    ("Interest income from lending by an NBFC is exempt from GST",
     "but fee-based income such as processing or commission charges is taxable at 18 percent",
     "Is all NBFC income GST-exempt, or is some of it taxable?",
     "processing"),
    ("Co-lending loan-share transfer must occur within the stipulated window",
     "but the transfer may be deferred where the blended interest computation is pending, if documented",
     "Can the co-lending transfer ever be deferred beyond the normal window?",
     "deferred"),
]

# HARD distractors: same topics, similar wording, NO carve-out (to confuse retrieval).
_HARD = [
    "Co-lending arrangements require careful structuring of funding shares between partner lenders.",
    "P2P platforms must maintain transparent records of every lender and borrower interaction.",
    "Loan disbursal processes should be auditable and traceable end to end for every account.",
    "Boards are expected to maintain robust governance over compliance and risk functions.",
    "Quarterly returns form part of the periodic supervisory reporting obligations of entities.",
    "Customer data handling must follow strong security and access-control practices throughout.",
    "Changes in ownership of regulated entities attract heightened supervisory attention generally.",
    "Customer onboarding workflows must balance speed with adequate due-diligence checks.",
    "The taxation of financial services depends on the precise nature of each revenue stream.",
    "Operational timelines in lending arrangements should be defined clearly in the agreement.",
]


def toks(s: str) -> int:
    return max(1, len(s) // 4)


def gemma(prompt: str, key: str, retries: int = 4) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/{MODEL}:generateContent?key={key}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.0, "maxOutputTokens": 120}}).encode()
    for a in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            return d["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(3 * (a + 1)); continue
            return f"[HTTP {e.code}]"
        except Exception as e:
            time.sleep(2);
            if a == retries - 1:
                return f"[ERR {type(e).__name__}]"
    return "[RATE-LIMITED]"


def main() -> None:
    key = next(l.split("=", 1)[1].strip() for l in open(".env") if l.startswith("GOOGLE_API_KEY="))
    from sentence_transformers import SentenceTransformer
    import torch; torch.set_num_threads(1)
    enc = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")

    target_full = [f"{m}. {c}." for (m, c, _, _) in ITEMS]
    target_main = [m for (m, _, _, _) in ITEMS]
    target_cond = [c for (_, c, _, _) in ITEMS]
    queries = [q for (_, _, q, _) in ITEMS]
    gold = [g for (_, _, _, g) in ITEMS]
    n = len(ITEMS)
    distract = [_HARD[i % len(_HARD)] + f" (ref {i})" for i in range(N_DISTRACT)]

    E = enc.encode(target_full + target_cond + queries + distract,
                   normalize_embeddings=True, show_progress_bar=False, batch_size=128)
    Ef, Ec, Eq, Ed = E[:n], E[n:2*n], E[2*n:3*n], E[3*n:]

    def assemble_vanilla(qi):
        Dmat = np.vstack([Ef, Ed]); Dtxt = target_full + distract
        order = np.argsort(-(Dmat @ Eq[qi])); ctx, b = [], 0
        for idx in order:
            if b + toks(Dtxt[idx]) > BUDGET: break
            ctx.append(Dtxt[idx]); b += toks(Dtxt[idx])
        return " ".join(ctx)

    def assemble_dtcam(qi):
        order = np.argsort(-(Ec @ Eq[qi])); ctx, b = [], 0
        for idx in order:
            if b + toks(target_cond[idx]) > BUDGET: break
            ctx.append(target_cond[idx]); b += toks(target_cond[idx])
        return " ".join(ctx)

    def assemble_summary(qi):  # lossy: only main clauses (nuance dropped)
        gists = target_main + distract; ctx, b = [], 0
        for g in gists:
            if b + toks(g) > BUDGET: break
            ctx.append(g); b += toks(g)
        return " ".join(ctx)

    systems = {"SummaryMem(lossy)": assemble_summary, "VanillaRAG": assemble_vanilla, "DT-CAM": assemble_dtcam}
    PROMPT = ("Answer the question using ONLY the context below. Be specific. "
              "If the context does not contain the answer, reply exactly 'NOT FOUND'.\n\nContext:\n{ctx}\n\nQuestion: {q}\nAnswer:")

    results = {s: {"correct": 0, "notfound": 0, "rows": []} for s in systems}
    print(f"Model: {MODEL}  | items: {n} | hard distractors: {N_DISTRACT} | budget: {BUDGET} tok\n", flush=True)
    for s, fn in systems.items():
        for qi in range(n):
            ctx = fn(qi)
            ans = gemma(PROMPT.format(ctx=ctx, q=queries[qi]), key)
            al = ans.lower()
            nf = "not found" in al
            ok = (gold[qi].lower() in al) and not nf
            results[s]["correct"] += ok
            results[s]["notfound"] += nf
            results[s]["rows"].append((qi, ok, nf))
            time.sleep(0.4)
        c = results[s]["correct"]; nfc = results[s]["notfound"]
        print(f"  {s:<18} nuance-correct {c}/{n} = {c/n:.0%}   (NOT-FOUND: {nfc})", flush=True)

    print("\nPer-item (1=correct nuance answer):")
    print("  item  " + "  ".join(f"{s[:10]:>10}" for s in systems))
    for qi in range(n):
        cells = "  ".join(f"{int([r for r in results[s]['rows'] if r[0]==qi][0][1]):>10}" for s in systems)
        print(f"  {qi:>4}  {cells}")


if __name__ == "__main__":
    main()
