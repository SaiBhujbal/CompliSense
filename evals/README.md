# RBI-NormBench

A benchmark + scorer for the research thesis behind CompliSense:

> Existing RAG token-reduction methods optimize **average** accuracy. A compliance
> tool must instead guarantee **worst-case recall of normative obligations**
> (`shall` / `must` / thresholds / dates / section numbers). RBI-NormBench
> measures that, plus citation resolvability and calibrated abstention.

## Run

```bash
python -m evals.run_eval --mock     # self-check, no API keys / corpus needed
python -m evals.run_eval            # real CompliSense pipeline (needs keys + ingested corpus)
python -m evals.run_eval --judge    # add an LLM judge for fuzzy obligation matching
```

`--mock` uses intentionally-flawed canned answers (a missed obligation + a
fabricated citation) so you can confirm the scorer *catches* problems before
trusting it on the real system.

## Falsifiable success metric (the bar)

A run **PASSES** only if, on the held-out set:
- **normative-obligation recall (macro) ≥ 0.99** — every applicable `shall`/`must`/threshold/date is surfaced;
- **behavior accuracy = 1.0** — answers when it should, abstains when out-of-corpus;
- **citation-resolvable rate = 1.0** — every `[S#]` resolves to a real retrieved source (no fabricated citations).

Token usage (in/out) is recorded so a compression method can be evaluated on
**token reduction at fixed recall** — the actual research claim. A method that
cuts tokens but drops recall below the floor **fails**, by design.

## Item schema (`dataset/rbi_normbench.jsonl`, one JSON object per line)

| field | meaning |
|---|---|
| `question` | the user query |
| `expected_behavior` | `"answer"` or `"abstain"` (out-of-corpus) |
| `required_obligations[]` | each `{id, summary, key_facts[], source_hint}` — the obligations a correct answer MUST surface |
| `key_facts` | lowercased load-bearing substrings (e.g. `"26%"`, `"5%"`); deterministic match. Leave empty to require the `--judge` path |
| `must_cite_source_like[]` | the cited source title/ref should contain one of these |
| `provenance` | `verified_web` \| `expert_label_required` \| `synthetic_template` |

## Labeling protocol (how to grow this to a real benchmark)

1. Write a realistic founder/CFO/analyst question.
2. Open the **actual RBI source** and extract each normative obligation a correct
   answer must contain. For each, set `key_facts` to the minimal load-bearing
   tokens (percentages, amounts, dates, section refs) — not prose.
3. Set `source_hint` and `must_cite_source_like` to the document it comes from.
4. Set `provenance`:
   - `expert_label_required` until a qualified professional has verified it
     (such items are **excluded** from recall scoring — `key_facts` empty).
   - `verified_web` once grounded in a primary source online.
   - `expert_verified` once a compliance professional signs off (treat as ground truth).
5. Add `abstain` items for out-of-corpus questions to test calibrated refusal.
6. **Target ≥200 expert-verified items** before any "without missing data" claim
   is defensible.

## ⚠️ Honest status

The seed items are **web-verified, NOT legal-expert-verified**. They are a
scaffold to make the metric runnable — **not legal ground truth**. No obligation
here should be relied upon for actual compliance until a qualified professional
validates it. The benchmark's value is the *method of measurement*; its
authority depends entirely on the labeling that follows.
