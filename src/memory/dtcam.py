"""
DT-CAM core + the lossy-reflection baseline (stdlib only — runs anywhere).

Both memories ingest passages, "consolidate" (the meditation/sleep step), then
answer a later CUE by assembling context. The difference is the whole thesis:
  - LossyReflectionMemory: consolidation keeps the main clause and DROPS the
    subordinate conditional ("... but may be used as an extra"). Detail is gone
    permanently (mirrors Generative-Agents reflection / summary-memory).
  - DualTraceMemory: conditional/normative spans are DEMOTED to a dormant tier
    (zero standing token cost) with a tiny stub left in the active gist; a cue
    pattern-completes back to the dormant episode, recovering the nuance.

This is a MECHANISM demo: retrieval/answer use keyword matching, not embeddings/
PPR/an LLM. A production version swaps in HippoRAG-style PPR + a real classifier
+ an LLM answerer. The point is to show the recovery gap cheaply and falsifiably.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Cue phrases that mark a CONDITIONAL carve-out (the nuance lossy summary kills).
_CONDITIONAL_RE = re.compile(
    r"\b(but|however|except|unless|provided that|optional\w*|may (also|be)|"
    r"can be|could be|in addition|additional\w*|as an extra|where applicable|only if)\b",
    re.IGNORECASE,
)
# NRPC-style normative markers.
_NORMATIVE_RE = re.compile(
    r"\b(shall|must|mandatory|prohibit\w*|require\w*|permitted|cap\w*)\b|\d|%|₹|\bcrore\b|\blakh\b",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"(?<=[.;])\s+")
_STOP = set("the a an of to in for and or is are be on with as at by from this that "
            "any all can could may be used a need needs do does is there".split())


def _tokens(s: str) -> int:
    return max(1, len(s) // 4)


def classify_span(span: str) -> str:
    """conditional > normative > boilerplate (conditional wins — it's the nuance)."""
    if _CONDITIONAL_RE.search(span):
        return "conditional"
    if _NORMATIVE_RE.search(span):
        return "normative"
    return "boilerplate"


def _keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 2}


def _split(passage: str) -> list[str]:
    return [s.strip() for s in _SPLIT_RE.split(passage) if s.strip()]


@dataclass
class Episode:
    text: str
    tag: str
    keywords: set[str] = field(default_factory=set)


# --------------------------------------------------------------------------- #
# Baseline: lossy reflection (gist replaces detail)
# --------------------------------------------------------------------------- #
class LossyReflectionMemory:
    def __init__(self) -> None:
        self.gist: list[str] = []

    def ingest_and_consolidate(self, passages: list[str]) -> None:
        self.gist = []
        for p in passages:
            for span in _split(p):
                if classify_span(span) == "conditional":
                    # Reflection keeps the main clause, drops the subordinate
                    # conditional ("... but/except/unless ..."). Detail LOST.
                    main = re.split(_CONDITIONAL_RE, span, maxsplit=1)[0].strip()
                    if main:
                        self.gist.append(main)
                    # the conditional carve-out is simply discarded
                else:
                    self.gist.append(span)

    def context_for(self, cue: str) -> str:  # no cue recovery — it's gone
        return " ".join(self.gist)

    def recoverable_corpus(self) -> str:  # everything the memory still holds
        return " ".join(self.gist)

    def standing_tokens(self) -> int:
        return sum(_tokens(g) for g in self.gist)

    def query_tokens(self, cue: str) -> int:
        return self.standing_tokens()


# --------------------------------------------------------------------------- #
# DT-CAM: dual-trace, demote-not-delete
# --------------------------------------------------------------------------- #
class DualTraceMemory:
    def __init__(self, use_cue_recovery: bool = True) -> None:
        self.gist: list[str] = []
        self.dormant: list[Episode] = []  # zero standing token cost
        self.use_cue_recovery = use_cue_recovery  # ablation switch

    def ingest_and_consolidate(self, passages: list[str]) -> None:
        self.gist, self.dormant = [], []
        for p in passages:
            for span in _split(p):
                tag = classify_span(span)
                if tag == "conditional":
                    # DEMOTE to dormant (verbatim), leave a cheap stub in gist.
                    ep = Episode(span, tag, _keywords(span))
                    self.dormant.append(ep)
                    self.gist.append(f"[conditional carve-out #{len(self.dormant)-1}]")
                elif tag == "normative":
                    self.gist.append(span)  # normative stays in active gist
                else:
                    self.gist.append(span)  # (a real system would compress this)

    def context_for(self, cue: str) -> str:
        ctx = list(self.gist)
        if self.use_cue_recovery:
            ck = _keywords(cue)
            for ep in self.dormant:
                if ep.tag == "conditional" and ck & ep.keywords:  # pattern completion
                    ctx.append(ep.text)
        return " ".join(ctx)

    def recoverable_corpus(self) -> str:  # nothing is permanently lost
        return " ".join(self.gist + [ep.text for ep in self.dormant])

    def standing_tokens(self) -> int:  # dormant tier is NOT resident
        return sum(_tokens(g) for g in self.gist)

    def query_tokens(self, cue: str) -> int:
        return sum(_tokens(s) for s in self.context_for(cue).split(". "))
