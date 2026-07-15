# Regulatory Memory Consolidation (RMC)
### Budget-bounded "back-of-mind" memory with verbatim normative guarantees and amendment-aware invalidation

**Status:** research design v1 (2026-07-02) · **Target:** top applied venue (COLM / EMNLP / TACL-applied); Q1 *possible*, not promised — see Honesty section.

**Motivating failure (owner's framing, and the whole point):** summarization destroys *conditional knowledge*. "X is good — **but in scenarios Y and Z, G is the better choice**" gets consolidated to "X is good"; the carve-out is deleted, and the memory is now *confidently wrong in exactly the situations that matter*. Our own measurement confirms it: a lossy reflection/summary memory recovered **0%** of such conditional carve-outs (permanent loss), while the dual-trace demote-not-delete design recovered **100%** at ~1.06× standing tokens (`evals/nruc_eval.py`; the gain is carried by associative cue recovery — ablation drops it to 0%). RMC's goal in one line: **the fewest resident tokens that still guarantee the letter of the law and the carve-outs — noise compressed, knowledge never.**

---

## 1. The honest starting point: what is already taken

The intuitive framings — "let the LLM meditate on its memory" and "compress context but keep provenance" — are **already published**. Claiming them is a desk-reject.

| Your concept | Closest prior art | What they already do |
|---|---|---|
| "Meditation" / offline knowledge improvement | [Sleep-Like Memory Consolidation in LLMs](https://www.emergentmind.com/papers/2605.26099), [LLMs Need Sleep](https://www.emergentmind.com/papers/2606.03979) | Offline consolidation passes convert context → persistent memory; big token/runtime savings (up to 117×/12× claimed) |
| "Back of mind" tiered memory | [From Lossy to Verified: Provenance-Aware Tiered Memory](https://arxiv.org/html/2602.17913), [TiMem](https://arxiv.org/pdf/2601.02845), [LightMem](https://arxiv.org/html/2510.18866v1) | Tiered memory with provenance pointers, verified write-back, −54% input tokens |
| Budget-bounded memory | [BudgetMem](https://arxiv.org/pdf/2511.04919) | Learned selective memory policies for cost |
| Noise-free consolidation | MaRS / [Forgetful but Faithful](https://arxiv.org/html/2512.12856) | Typed memory nodes w/ provenance + principled removal |

**Conclusion of the audit:** generic sleep-consolidation and provenance-preserving compression are occupied. The contribution must be *narrower, harder, and eval-anchored*.

## 2. The surviving gap (what nobody in that list does)

All prior consolidation work treats memory items as *semantically fungible summaries*: it preserves **pointers** to sources, but not **the letter of the source**. In regulated domains that is fatal — "₹10 cr NOF by Mar 2027" paraphrased as "about ten crore by 2027" is a *legally wrong memory* with a perfectly valid provenance pointer.

And no found work invalidates memory on **upstream document amendment**: their freshness = recency; regulatory freshness = *legal validity*. RBI amends Master Directions constantly; a consolidated memory must die when its source clause dies, not when it gets old.

### The three claimed contributions
1. **Verbatim-span invariants (VSI).** Consolidation may compress aggressively *except* normative spans (thresholds, dates, "shall" clauses, section numbers), which must survive **verbatim** through any number of consolidation cycles. Deterministically checkable (regex/span-match — extends our NRPC span detector). *"Lossy everywhere, lossless where the law lives."*
2. **Amendment-aware invalidation (AAI).** Every consolidated trace carries (source-doc, version/date, clause-anchor). An ingest-time diff of a re-fetched corpus marks affected traces INVALID and queues re-consolidation. Memory lifecycle is coupled to *legal validity semantics*, not recency. (Black-hat check: "isn't this cache invalidation?" — mechanically yes; the novelty is the validity-semantics coupling + measuring the harm it prevents.)
3. **Citation-gated write-back under budget (CGW).** A trace is committed to back-of-mind memory only if (a) its [S#] citations resolve deterministically against the source (reuse the faithfulness gate) and (b) it fits a hard token budget. Headline metric: **normative recall per 1k tokens per ₹.**

The "meditation" concept survives as the *scheduler*: idle-time consolidation cycles that (re)compress the hot memory under VSI+CGW and process the AAI invalidation queue — i.e., meditation with a legal conscience and a budget.

## 3. Benchmark: RBI-NormBench (the moat)

No public benchmark measures *verbatim normative recall under memory consolidation*. Build it from our 1592-chunk RBI corpus:
- **Queries:** N≈200 questions whose answers are legally material spans (thresholds, deadlines, obligations), stratified by direction (KYC/SBR/PA/DL/AA).
- **Amendment set:** M≈40 simulated amendments (edit a threshold/date in the source; the correct answer changes).
- **Metrics:** (1) Verbatim normative recall (exact span match); (2) citation-resolution rate; (3) tokens/query & $ per 100 queries; (4) **staleness error rate** post-amendment (unique to us); (5) end answer accuracy (LLM-judged, secondary).

## 4. Falsifiable hypotheses & killer baselines

- **H1:** RMC ≥ full-context RAG on normative recall at ≤40% of its tokens/query.
- **H2:** Generic compression (LLMLingua-class) loses ≥15pp verbatim normative recall vs RMC at equal budget.
- **H3:** After amendments, recency-based memories answer ≥30% of affected queries stale; AAI cuts that to <5%.
- **Baselines (all mandatory, incl. the killer lossless one):** (a) full-context vanilla RAG (lossless ceiling), (b) LLMLingua-2 compression, (c) provenance-tiered memory *without* VSI/AAI (ablation ≈ prior art), (d) CAG preload, (e) RMC full. Ablate VSI, AAI, CGW independently.
- **Kill criterion (pre-registered):** if (c) matches RMC on normative recall within 2pp at equal budget, the contribution collapses to the benchmark alone — publish NormBench as a resource paper instead.

## 5. Budget-bounded experiment plan

Free/cheap by construction: consolidation runs offline on Groq qwen3.6-27b (fast, JSON-mode) or flash-lite; embeddings local (bge-small); deterministic checks are free. Est. <$15 total for the full grid (5 systems × 200 queries × 3 seeds, plus consolidation passes) at current Groq pricing. Harness: extend `evals/` (NormBench runner + amendment simulator + cost meter). No training; all inference-time — reproducible on free tiers.

## 6. Critique (Socratic + Six Hats, condensed)

- **Socratic — "what do we mean by *remember*?"** For a compliance copilot, remembering = *being able to re-emit the exact governing span with a resolvable citation*. This definition is the whole design; if reviewers accept it, VSI follows necessarily. Make it §1 of the paper.
- **White:** consolidation savings claims in prior work (117×, 54%) set the bar; we must report the same axes.
- **Black (top risks):** (1) VSI may be dismissed as "just don't compress some spans" — counter with the ablation showing generic methods *do* corrupt them; (2) simulated amendments may look synthetic — mitigate with ≥10 *real* historical RBI amendments; (3) single-domain scope — position as regulated-domain memory, invite replication in tax/medical.
- **Yellow:** the CompliSense product IS the demo; every experiment doubles as product hardening (faithfulness gate, NRPC, corpus already exist — ~60% of the system is built).
- **Green (stretch, only if H1-H3 hold):** "interference audit" — measure whether consolidating *similar* directions (e.g. two NBFC circulars) cross-contaminates thresholds; no prior memory paper measures regulatory cross-contamination.
- **Honesty (the part that matters):** *Q1 cannot be promised.* Realistic: strong applied paper if H2/H3 land with big margins; resource paper (NormBench) as the floor. The differentiator reviewers can't take away is the benchmark + the validity-semantics framing.

## 7. Position within our OWN prior work (do not restart the thread)

Past sessions already stress-tested this space and produced artifacts + a meta-lesson:
- **DT-CAM** (`src/memory/dtcam.py` + `evals/nruc_eval.py`): demote-not-delete dual-trace memory. Verified: lossy summary-memory loses 100% of conditional nuance; DT-CAM recovers 100% — but the **ablation showed the associative cue recovery carries the gain**, and DT-CAM only *ties* strong vanilla retrieval on recall. It is the "back-of-mind" layer of RMC, already built.
- **MCA-Reg** (`src/arbitration/mca.py`): mutability-aware arbitration. Genuine pilot finding: mutability is decodable within-dataset (~0.76 AUC) but is **relation-bound and does not transfer** (OOD AUC ≈ chance) — a real cautionary result worth firming up separately.
- **Meta-lesson (verified 3×):** new-paradigm ideas conjured in chat get demoted by prior art (mutability-arbitration, DT-CAM-as-paradigm, RVRM). Execution beats ideation here.

**What RMC adds that our own thread did not have:** (1) **AAI — amendment-aware invalidation** and its *staleness-error metric* (the genuinely untouched angle; nothing in our notes or the literature ties memory lifecycle to legal-validity semantics); (2) the **budget/cost axis** ($ per 100 queries) as a first-class reported metric; (3) packaging DT-CAM + NRPC/VSI + faithfulness-gated write-back into ONE evaluated system against the killer lossless baseline. VSI itself is our existing HOT/COLD design promoted to a measured claim — incremental, and must be framed as such.

## 8. Executed results (2026-07-02) — what's real so far

- **Step 1 done:** grounding checker + amendment simulator (`evals/normbench_ground.py`). 11/17 obligations verbatim-grounded (topic-guard kills spurious matches); 6 simulated amendments generated.
- **Step 2 done:** meditation scheduler (`src/memory/rmc.py`) — mechanism-verified on the real corpus: VSI cued recall 100% / recoverable 100% vs LossyHead 9%; CGW rejected 6/6 fault-injected drifts; **AAI 100% fresh vs recency-baseline 0%**. DEEP (back-of-mind) mode: **10,808 → 1,209 resident tokens (−89%) at 100% cued recall** (small-pool).
- **REAL amendments mined** (`evals/dataset/normbench_amendments_real.jsonl`): 9 dated, sourced regulatory changes — co-lending retention **20%→10%** (eff. 2026-01-01), co-lending scope priority-sector→all, DLG digital-only→all-lending, DLG 5% cap introduced (Jun 2023), P2P ₹50L CA-certificate + T+1 escrow (Aug 2024), SBR NOF glide 2→5→10 cr, PA net-worth 15→25 cr. 5/9 exercisable against the current corpus. This upgrades AAI's eval from simulated to REAL external validity.
- **Scaling result (the honest one, `evals/experiments/recovery_scale.py`):** span-level cue recovery COLLAPSES at scale (4,882 spans): keyword 64%@k=40, embedding *worse* at 55%. Trace-level embedding recovery: 73%@k=3 (~565 tok/q), plateaus at 73% — a bge-small encoder ceiling. **Design consequence:** DEEP-mode recovery must be the existing HYBRID (BM25+dense) retriever scoped to dormant traces, not a bespoke recovery mechanism. The paper reports this as a measured negative→fix arc — reviewers reward it.
- **Groq grid:** run 1 invalid (TPM contamination — documented); resumable harness with 8k-TPM pacing + missing-data accounting running.

## 9. Path to conference-grade (the last mile, in order)
1. **Hybrid trace-recovery experiment** — close the 73% plateau with BM25+dense recovery (local, free); report the recovery-frontier plot (recall vs tokens/query — the money figure).
2. **Real-amendment AAI eval** — re-run the staleness eval on the 5 corpus-exercisable REAL amendments (needs Co-Lending 2025 + P2P 2024 PDFs ingested to unlock the other 4).
3. **Scale NormBench** to ≥100 items (mine obligations from all 7 corpus docs with the topic-guard pipeline + expert pass), report CIs over ≥3 seeds.
4. **Real LLMLingua-2 baseline** (replace the stand-in) + provenance-tiered reimpl; complete the pre-registered grid on a paid tier (the free-tier TPM makes full grids impractical).
5. **The Pareto frontier claim** to lead the paper: *resident-tokens vs verbatim-normative-recall vs staleness* — RMC's point (−89% tokens, 100% recall, 0% stale) vs every baseline's.
