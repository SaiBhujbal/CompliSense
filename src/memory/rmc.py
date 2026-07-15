"""RMC — Regulatory Memory Consolidation (the "meditation" scheduler).

Composes the session's verified building blocks into ONE memory lifecycle
(research/REGULATORY_MEMORY_CONSOLIDATION.md, step 2 — mechanism layer, zero-API):

  ingest(chunks)                    raw episodes -> HOT buffer (full tokens)
  meditate()                        consolidation cycle:
     VSI  : normative sentences survive VERBATIM (NRPC classifier);
            conditionals demote to a DORMANT tier (DT-CAM, recoverable);
            boilerplate is budgeted down (keep_ratio).
     CGW  : citation-gated write-back — a trace commits ONLY if every
            normative span still exact-matches its SOURCE text (the
            deterministic faithfulness check applied at write time).
  apply_amendment(...)              AAI: traces whose provenance contains the
            amended surface are INVALIDATED and re-consolidated from the
            amended source — memory freshness = legal validity, not recency.

Deterministic on purpose (like NRPC/DT-CAM): the claim this layer supports is
that the INVARIANTS and LIFECYCLE hold end-to-end; LLM-quality consolidation
gains are step 3 (pre-registered grid on Groq).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..rag.compression import _approx_tokens, _split, is_normative
from .dtcam import _CONDITIONAL_RE, _keywords


@dataclass
class Trace:
    """One consolidated memory trace with provenance."""

    trace_id: int
    source: str
    page: object
    gist: str                       # active tier (resident tokens)
    norm_spans: list[str]           # VSI invariant set — must stay verbatim
    dormant: list[str] = field(default_factory=list)  # demoted, recoverable
    valid: bool = True
    version: int = 0


@dataclass
class MeditationReport:
    episodes_in: int = 0
    committed: int = 0
    rejected_cgw: int = 0
    tokens_before: int = 0
    tokens_after: int = 0

    @property
    def reduction(self) -> float:
        return 1.0 - self.tokens_after / self.tokens_before if self.tokens_before else 0.0


class RMCMemory:
    def __init__(self, keep_ratio: float = 0.10, fault_hook=None,
                 deep: bool = False) -> None:
        self.keep_ratio = keep_ratio
        self.hot: list[tuple[str, str, object]] = []   # (text, source, page)
        self.traces: list[Trace] = []
        self.invalidation_log: list[dict] = []
        # deep ("back-of-mind") mode: EVERYTHING demotes to dormant — the active
        # gist is only a tiny keyword stub per trace. Verbatim spans come back
        # via cue recovery. Minimum resident tokens, zero knowledge deletion.
        self.deep = deep
        # test seam: fault_hook(gist)->gist lets the eval corrupt a trace to
        # prove CGW actually rejects drifted write-backs.
        self._fault_hook = fault_hook

    # ------------------------------------------------------------------ #
    def ingest(self, chunks: list[tuple[str, str, object]]) -> None:
        self.hot.extend(chunks)

    def _consolidate_one(self, text: str, source: str, page: object) -> Trace:
        sentences = _split(text)
        norm, dormant, boiler = [], [], []
        for s in sentences:
            if is_normative(s):
                norm.append(s)                       # VSI: verbatim, always
            elif _CONDITIONAL_RE.search(s):
                dormant.append(s)                    # demote-not-delete
            else:
                boiler.append(s)

        if self.deep:
            # Back-of-mind: verbatim spans live dormant; the resident gist is a
            # keyword stub just big enough to say "something lives here".
            dormant = norm + dormant + boiler
            kws = sorted(set().union(*(_keywords(s) for s in norm)) if norm else set())
            gist = f"[{source} p.{page}: " + " ".join(kws[:12]) + "]"
            return Trace(len(self.traces), source, page, gist, list(norm), dormant)

        budget = _approx_tokens(text) * self.keep_ratio
        kept, used = [], 0
        for s in boiler:
            t = _approx_tokens(s)
            if used + t <= budget:
                kept.append(s)
                used += t
            else:
                dormant.append(s)                    # over budget -> dormant, not deleted
        gist = " ".join(norm + kept)
        return Trace(len(self.traces), source, page, gist, list(norm), dormant)

    def meditate(self, source_lookup: dict) -> MeditationReport:
        """One consolidation cycle over the HOT buffer (the 'meditation' step)."""
        rep = MeditationReport(episodes_in=len(self.hot))
        rep.tokens_before = sum(_approx_tokens(t) for t, _, _ in self.hot)
        still_hot = []
        for text, source, page in self.hot:
            trace = self._consolidate_one(text, source, page)
            if self._fault_hook is not None:
                trace.gist = self._fault_hook(trace.gist)
            # CGW: every normative span must still exist verbatim BOTH in the
            # trace's recoverable content (gist + dormant — deep mode keeps
            # spans dormant) AND in the source text it cites.
            src_text = (source_lookup.get((source, page)) or "").lower()
            held = (trace.gist + " " + " ".join(trace.dormant)).lower()
            ok = all(sp.lower() in held and sp.lower() in src_text
                     for sp in trace.norm_spans)
            if ok:
                self.traces.append(trace)
                rep.committed += 1
            else:
                still_hot.append((text, source, page))   # refused write-back
                rep.rejected_cgw += 1
        self.hot = still_hot
        rep.tokens_after = self.standing_tokens()
        return rep

    # ------------------------------------------------------------------ #
    def apply_amendment(self, source: str, old_surface: str, new_surface: str,
                        source_lookup: dict) -> int:
        """AAI: invalidate every trace from `source` that carries the amended
        surface, then re-consolidate those chunks from the (amended) lookup.
        Returns the number of traces invalidated."""
        n = 0
        for tr in self.traces:
            if not tr.valid or tr.source != source:
                continue
            carrier = (old_surface.lower() in tr.gist.lower()
                       or any(old_surface.lower() in sp.lower() for sp in tr.norm_spans))
            if carrier:
                tr.valid = False
                n += 1
                self.invalidation_log.append({
                    "trace_id": tr.trace_id, "source": source,
                    "old": old_surface, "new": new_surface,
                })
                amended = source_lookup.get((tr.source, tr.page))
                if amended:
                    self.hot.append((amended, tr.source, tr.page))  # re-meditate queue
        return n

    # ------------------------------------------------------------------ #
    def context(self, cue: str = "") -> str:
        """Valid active gists + cue-recovered dormant spans (DT-CAM recovery)."""
        parts = [tr.gist for tr in self.traces if tr.valid]
        if cue:
            ck = _keywords(cue)
            for tr in self.traces:
                if tr.valid:
                    parts += [d for d in tr.dormant if ck & _keywords(d)]
        return " ".join(parts)

    def recoverable(self) -> str:
        """Everything not permanently lost (valid gists + all dormant)."""
        return " ".join(tr.gist + " " + " ".join(tr.dormant)
                        for tr in self.traces if tr.valid)

    def standing_tokens(self) -> int:
        return sum(_approx_tokens(tr.gist) for tr in self.traces if tr.valid)


class RecencyMemory(RMCMemory):
    """Ablation baseline: identical consolidation, NO amendment invalidation —
    freshness = recency, the prior-art default. Serves stale law after amendments."""

    def apply_amendment(self, *args, **kwargs) -> int:  # noqa: D401
        return 0  # recency-based memory ignores upstream amendments
