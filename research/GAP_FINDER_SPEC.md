# Gap Finder — Spec

**One-liner:** Turn a competitor's reviews into a ranked, *cited* list of attackable weaknesses, and for the top one, a finance-gated positioning move. The engine that fills the "crack in the wall" visual with real data.

> Design principle: this is only a product if it is **evidence-gated and honest about what is a real opening vs. a mirage.** The naive version ("reviews say dryness → make it moisturizing → win") gives confident bad advice. Every stage below exists to prevent that.

---

## 1. Inputs

- **Target competitor** — brand / product (1+).
- **User's product context** — sector, price band, positioning, and (if uploaded) their own P&L/margins. Drives the finance gate.
- **Sector** — drives which review corpora and which benchmarks apply.

## 2. Data sources per sector (groundability map)

Each source must yield **volume + rating + timestamp** (a denominator) or it doesn't qualify. Use official APIs / permitted data — **no scraping dependency**, ToS-safe.

| Sector | Primary review corpora | Richness | Fallback when thin |
|---|---|---|---|
| Beauty / personal care | Nykaa, Amazon, Tira, Myntra, Sephora | **Rich** | — |
| Consumer electronics / gadgets | Amazon, Flipkart, app stores, + named-critic lane (YouTube) | **Rich** | — |
| Packaged food / FMCG | Amazon, BigBasket, Zepto, Trustpilot | Medium | brand/price/claims compare |
| Apps / consumer fintech | Play Store, App Store, Trustpilot | Medium–Rich | — |
| B2B / SaaS | G2, Trustpilot, Capterra | Medium | feature + pricing compare |
| Regulated finance products / services | G2, Trustpilot, forums | **Thin** | fall back to feature/pricing/filing compare; **flag low sentiment coverage — do not fabricate** |

Honesty rule: where review data is thin, the tool **says so** and degrades to grounded feature/pricing comparison. It never invents sentiment.

## 3. Pipeline (cluster → quantify → classify → finance-gate → position)

**A. Ingest** — pull competitor reviews as `{rating, text, date, verified?, source, url}`; store with provenance.

**B. Cluster** — embedding-cluster review text into **complaint themes** and **praise themes**; label each. Output themes with member counts.

**C. Quantify** *(denominators mandatory — no "many reviews say")* — per theme:
- share of negative reviews (% of N), absolute volume, **trend over time**
- avg rating of reviews mentioning it
- correlation with rating drops / reformulation events / return signals

**D. Classify the gap** *(the crucial step — separates product from gimmick)* — tag each weakness theme:
- **Fixable gap** — solvable without destroying the core benefit → *attackable*.
- **Inherent tradeoff** — solving it sacrifices a top *praise* theme (e.g. "deep clean" ⇄ "dryness" is chemistry) → **flag, don't chase**.
- **Vocal minority** — high salience, low share, fans unbothered → **de-prioritize**.

*How:* cross-check each complaint theme against the top praise themes (conflict ⇒ tradeoff), apply a share threshold, and read the rating distribution.

**E. Finance-gate + defensibility** — for each Fixable gap:
- dissatisfied-segment size = share × est. category volume (sourced or flagged)
- fix cost = COGS / eng delta (estimate, flagged)
- price / return-rate impact
- **copy-back risk** — can the incumbent replicate cheaply? Easy reformulation = low moat; requires a tradeoff or repositioning they won't make = higher moat.
- → **wedge score = fixable × market-size × defensibility**, every factor sourced or flagged.

**F. Positioning move** — for the top wedge: the product recommendation + the customer-facing positioning line, grounded in the cited cluster. All rendered through the **provenance lens** (sourced / estimate / unverified).

## 4. Output data contract

```json
{
  "competitor": "...", "product": "...", "review_n": 1240, "as_of": "2026-07-09",
  "weaknesses": [
    {
      "theme": "dryness / tightness",
      "share_pct": 34, "volume": 190, "trend": "rising since Mar reformulation",
      "avg_rating": 2.1, "class": "fixable|tradeoff|vocal_minority",
      "conflicts_with_praise": ["deep clean"],
      "evidence": [{"id":"S1","title":"Nykaa review cluster","ref":"https://..."}]
    }
  ],
  "top_wedge": {
    "theme": "dryness / tightness",
    "market_size_est": "~X% of ₹Y category", "fix_cost_est": "+₹Z COGS (est.)",
    "copy_back_risk": "medium — reformulation is easy but cannibalizes their 'clinical' positioning",
    "wedge_score": 0.0,
    "product_move": "moisture-retaining surfactant; keep the deep-clean claim",
    "positioning_line": "The deep clean — without the tightness.",
    "sources": [{"id":"S1","title":"...","ref":"https://..."}]
  }
}
```

This object hydrates the UI and flows straight through `csRenderProvenance`.

## 5. UI — fills the crack visual (competitors.html)

- The incumbent **wall block** shows their *strength* (top praise themes).
- The **crack** = the top **fixable** weakness, quantified inline ("34% cite dryness · ↑ since Mar").
- **Zoom into the crack** → the **wedge panel**: cited review cluster → classifier tag → finance gate (market / fix cost / copy-back) → the positioning line. Every claim via the provenance lens.
- **Ranked weakness list** with class chips: `fixable` (teal) · `tradeoff` (amber) · `vocal-minority` (grey) — mirages are shown but visibly demoted.
- Per-weakness **"Ask AI"** deep-dive (reuses the inline panel).

## 6. Honesty guardrails (baked in, non-negotiable)

1. Denominators always shown (share of N, not "many").
2. Tradeoff / vocal-minority weaknesses shown but **de-prioritized** — never chased.
3. **Copy-back risk always stated** — not every crack is a durable wedge.
4. Thin-data sectors flagged; degrade to grounded compare, never fabricate sentiment.
5. ToS-safe sources only; no scraping dependency.

## 7. Build phases

- **Phase 1 (demo-grade, verifiable now):** curated/cached review dataset for 1–2 showcase competitors → full pipeline offline → crack UI. No live scraping, no quota dependency → **LinkedIn-ready and testable in preview.**
- **Phase 2:** live review ingestion via official APIs, per sector.
- **Phase 3:** the Competitor agent emits the gap structure directly (ties to the agent-level claim-tagging work).

## 8. Risks / open questions

- **Classifier D is the hardest and highest-value part** (fixable vs tradeoff vs minority) and the most error-prone → keep a human-in-the-loop check for v1.
- Clustering quality degrades on small review sets → require a minimum-N before showing a gap.
- LLM cost/latency for clustering → batch offline, cache.
- Per-platform review ToS → legal review before Phase 2.
