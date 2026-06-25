"""
NRPC — Normative-Recall-Preserving Compression.

The research idea (see memory/complisense-agent-topology.md): general RAG
compression optimizes *average* fidelity; a compliance tool must never drop a
normative obligation. NRPC classifies each sentence as NORMATIVE (carries a
modal verb, a number/amount/%, a date, or a section/clause reference) or
NON-NORMATIVE (marker-free prose), keeps every normative span verbatim, and
drops non-normative spans down to a token budget.

Rule-based on purpose: interpretable, model-agnostic, no training. The novelty
claim is NOT the technique — it's the *guarantee* (normative spans are never
dropped) and that it's measured against a normative-recall benchmark
(evals/nrpc_eval.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Broad on purpose: for a recall GUARANTEE, false positives (keeping a span) are
# safe; false negatives (dropping a normative span) are not. Err toward keeping.
_MODAL_RE = re.compile(
    r"\b(shall|must|mandatory|mandate\w*|prohibit\w*|require\w*|"
    r"permit\w*|allow\w*|eligib\w*|entitle\w*|exempt\w*|cap(?:ped|s)?|"
    r"not permitted|may not|shall not|obligation|penal\w*|liable)\b",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"(\d|%|₹|\bcrore\b|\blakh\b|\bper ?cent\b|\bbasis points?\b|\bbps\b)", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(19|20)\d{2}\b|\b(january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b",
    re.IGNORECASE,
)
_REF_RE = re.compile(
    r"\b(section|para|paragraph|clause|regulation|chapter|direction|annex\w*|schedule|sub-section)\b",
    re.IGNORECASE,
)

_SPLIT_RE = re.compile(r"(?<=[.;:])\s+|\n+")


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def is_normative(sentence: str) -> bool:
    """True if the span carries any normative marker (modal/number/date/ref)."""
    return bool(
        _MODAL_RE.search(sentence)
        or _NUM_RE.search(sentence)
        or _DATE_RE.search(sentence)
        or _REF_RE.search(sentence)
    )


def _split(text: str) -> list[str]:
    return [s.strip() for s in _SPLIT_RE.split(text) if s.strip()]


@dataclass
class CompressionStats:
    tokens_before: int
    tokens_after: int
    sentences_total: int
    normative_kept: int
    non_normative_kept: int
    non_normative_dropped: int

    @property
    def reduction(self) -> float:
        return 1.0 - (self.tokens_after / self.tokens_before) if self.tokens_before else 0.0


def compress_context(text: str, keep_ratio: float = 0.15) -> tuple[str, CompressionStats]:
    """Compress ``text`` while preserving ALL normative spans.

    ``keep_ratio`` = fraction of the ORIGINAL token budget to spend on
    non-normative sentences (0.0 drops all boilerplate). Normative spans are
    always kept, in original order.
    """
    sentences = _split(text)
    if not sentences:
        z = _approx_tokens(text)
        return text, CompressionStats(z, z, 0, 0, 0, 0)

    nonnorm_budget = _approx_tokens(text) * keep_ratio
    kept_nonnorm: set[int] = set()
    used = 0
    for idx, s in enumerate(sentences):
        if not is_normative(s):
            t = _approx_tokens(s)
            if used + t <= nonnorm_budget:
                kept_nonnorm.add(idx)
                used += t

    out, n_norm, n_nonnorm = [], 0, 0
    for idx, s in enumerate(sentences):
        if is_normative(s):
            out.append(s)
            n_norm += 1
        elif idx in kept_nonnorm:
            out.append(s)
            n_nonnorm += 1
    compressed = " ".join(out)

    total_nonnorm = sum(1 for s in sentences if not is_normative(s))
    stats = CompressionStats(
        tokens_before=_approx_tokens(text),
        tokens_after=_approx_tokens(compressed),
        sentences_total=len(sentences),
        normative_kept=n_norm,
        non_normative_kept=n_nonnorm,
        non_normative_dropped=total_nonnorm - n_nonnorm,
    )
    return compressed, stats
