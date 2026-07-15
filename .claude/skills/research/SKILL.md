---
name: research
description: Grounded finance-lens research playbook for CompliSense. Use for any market/competitor/PESTEL/SWOT/trend research, sentiment analysis, or head-to-head comparison. Enforces sourced-or-flagged claims, a fact-vs-inference wall, finance as the grounding lens across all sectors, and a source-quality hierarchy that keeps social noise out. Invoke whenever building an analysis a founder or analyst would rely on.
---

# Grounded Finance-Lens Research

CompliSense's only moat is trust: every output must be defensible. Free LLMs give confident, ungrounded answers — this skill exists so ours never does. Apply this playbook to all research: market, competitor, PESTEL, SWOT, trends, sentiment, and head-to-head comparison.

## Prime directive: sourced or flagged. Never invented.

Every factual claim carries one of two things:
- **A source** — a citable, retrievable origin (regulator filing, annual report, funding announcement, pricing page, review corpus with a URL).
- **An explicit gap flag** — `[no public data — estimate withheld]` or `[inference: <assumption stated>]`.

A confident number with no provenance is a defect, not an answer. An honest "we don't know this" is a feature — it's the thing free-LLM output never does.

## The fact / inference wall

Keep two lanes visibly separate. Never let one masquerade as the other.

- **FACT** — sourced and cited. "Slice raised $220M (cited)."
- **INFERENCE** — reasoning on top of facts, with the assumption named. "Implies ~18mo runway at estimated burn (assumption stated)."

When you state an inference, the reader must be able to see exactly which fact it rests on and which assumption you added.

## Finance is the grounding lens — across ALL sectors

The product is all-sector, but finance is not one domain among many — it is the discipline that forces groundability. Every analysis leg must **terminate in a quantifiable, sourced financial metric**, not a vibe.

- Generic PESTEL: "consumers care about sustainability." ❌ ungroundable vibe.
- Finance-lens PESTEL: "sustainable cotton raises COGS ~12%, cutting gross margin 62%→55% unless priced +8%; breakeven ~month 4 at current CAC/repeat." ✅ sourced, numeric, decision-useful.

For each dimension, ask: *what financial metric does this resolve into, and where is that number sourced?* Candidate metrics: COGS, gross/contribution margin, CAC, LTV, payback, runway, burn, capital intensity, cash-conversion cycle, take-rate, NPA/credit cost, regulatory/compliance cost.

**Benchmark data is the moat.** Per-sector benchmarks (typical margins, CAC, multiples) must come from the user's uploaded financials, public reports/filings, or cited industry data — never an LLM guess. If a benchmark can't be grounded, mark it an estimate; do not assert it.

## Source-quality hierarchy

Rank every source by four tests: **verifiable · quantifiable · hard-to-game · representative.**

1. **Primary / structured (prefer):** regulator filings (RBI circulars, RSS), annual reports, funding announcements, official pricing, app-store/Play/G2/Trustpilot reviews *with volume + trend + timestamp*. Passes all four tests.
2. **Named-critic lane (label, never score):** reputation-staked reviewers (e.g. expert YouTube/industry critics). Accountable and citable, but n=1 opinion — use as attributed qualitative insight (`"<critic> flagged X [link]"`), track sponsorship/bias, and **never aggregate into a numeric sentiment score.**
3. **Social noise (avoid as metric):** Instagram/ad comments, random social. Unverified, no denominator, adversarial (astroturf, deletion), unrepresentative. Use only as clearly-labeled anecdote (`[anecdote, not measured]`), never as data. This is the exact source category the customer distrusts — treating it as signal destroys the moat.

The differentiating move for sentiment is not "collect more noise" — it's **tie sentiment shifts to events** ("rating dropped 0.9★ the week fees rose / after RBI circular X"). Grounded, change-aware, on-thesis.

## Head-to-head comparison (competitor benchmarking)

When comparing the user's company vs. named rivals:
- Build a **matrix**: rivals × 6–8 dimensions. Each cell = value + source chip, or an honest `[no public data]`.
- **Decompose "better," never declare it.** No black-box "1 > 2." Show the axes; let the *user* set the weights; the overall verdict is the weighted roll-up of sourced axes.
- Make SWOT/PESTEL **relative** ("weaker than Cred on distribution; stronger than Slice on compliance posture") — a strength only exists against a benchmark.
- Lead with axes you can ground (licenses, funding, pricing, regulatory posture); treat fuzzy axes (CAC, margins) as clearly-marked estimates.

## Legal / IP guardrail

Do not reuse an employer's proprietary code, scrapers, datasets, or documented methodology — including rewriting it to disguise derivation. Rebuild commodity pipelines (e.g. review-sentiment) clean, from public principles. Respect platform ToS/copyright (YouTube, Meta): use official APIs within terms; don't build a dependency on scraped content.

## Recommended companions

Pair this skill with the installed thinking skills when stakes are high:
- **red-team** / **the-fool** — attack the analysis before reality does.
- **steelman** — build the opposing case to its strongest form before dismissing it.
- **thinking-fermi-estimation** — order-of-magnitude sanity checks on any estimated metric.
- **rag-architect** / **storm-research** — for retrieval design and multi-source synthesis.

## Output checklist (run before delivering)

1. Every number is sourced or flagged. No orphan claims.
2. Fact and inference are visibly separated.
3. Every analysis leg lands on a financial metric, or says why it can't.
4. No social-noise source is presented as a metric.
5. Comparisons decompose into weighted, sourced axes — no black-box verdict.
6. Gaps are stated plainly, not filled with plausible guesses.
