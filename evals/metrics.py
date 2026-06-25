"""Scoring for RBI-NormBench. Pure stdlib — runs without API keys or deps.

Headline metric is NORMATIVE-OBLIGATION RECALL (worst-case, per the research
thesis), alongside citation resolvability and abstention correctness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .schema import AnswerResult, BenchItem, Obligation

# Phrases that indicate the system declined to answer (grounded refusal).
_REFUSAL_MARKERS = [
    "could not find", "couldn't find", "won't guess", "will not guess",
    "unable to answer", "not in the provided", "no relevant", "cannot answer",
    "out of scope", "i'm focused on", "outside", "consult the rbi",
]

_CITE_RE = re.compile(r"\[(S\d+)\]")


def detect_abstention(result: AnswerResult) -> bool:
    if result.abstained:
        return True
    text = result.text.lower()
    return any(m in text for m in _REFUSAL_MARKERS)


def obligation_surfaced(ob: Obligation, text: str, judge=None) -> bool:
    """True if the obligation appears in the answer.

    Deterministic: ALL key_facts present (case-insensitive). If no key_facts
    (e.g. expert-label pending) fall back to the optional LLM judge, else False.
    """
    low = text.lower()
    if ob.key_facts:
        return all(kf.lower() in low for kf in ob.key_facts)
    if judge is not None:
        return bool(judge(ob.summary, text))
    return False


@dataclass
class ItemScore:
    id: str
    scorable: bool                 # False if obligations are expert-label-pending
    behavior_correct: bool
    obligation_recall: float
    missed_obligations: list[str] = field(default_factory=list)
    citations_resolvable: bool = True
    unresolved_citations: list[str] = field(default_factory=list)
    source_cited_ok: bool = True


def score_item(item: BenchItem, result: AnswerResult, judge=None) -> ItemScore:
    abstained = detect_abstention(result)
    expected_abstain = item.expected_behavior == "abstain"
    behavior_correct = abstained == expected_abstain

    # Citation resolvability: every [S#] used must resolve to a real source.
    cited = set(_CITE_RE.findall(result.text))
    valid = {s.get("id") for s in result.sources}
    unresolved = sorted(cited - valid)
    citations_resolvable = not unresolved

    # An item is "scorable" for recall only if it has real (key_facts-bearing)
    # obligations — placeholders awaiting expert labels don't count.
    real_obligations = [o for o in item.required_obligations if o.key_facts] if not judge \
        else item.required_obligations
    scorable = expected_abstain or bool(real_obligations) or not item.required_obligations

    if expected_abstain or not real_obligations:
        # Abstain items score on behavior; answer items with no real obligations
        # (expert-label pending) don't penalize recall.
        recall = (1.0 if behavior_correct else 0.0) if expected_abstain else 1.0
        return ItemScore(
            id=item.id, scorable=scorable, behavior_correct=behavior_correct,
            obligation_recall=recall, missed_obligations=[],
            citations_resolvable=citations_resolvable, unresolved_citations=unresolved,
            source_cited_ok=True,
        )

    hit, missed = 0, []
    for ob in real_obligations:
        if obligation_surfaced(ob, result.text, judge):
            hit += 1
        else:
            missed.append(ob.id)
    recall = hit / len(real_obligations)

    # Did it cite a plausibly-correct source?
    src_blob = " ".join(
        f"{s.get('title', '')} {s.get('ref', '')}" for s in result.sources
    ).lower()
    source_cited_ok = (not item.must_cite_source_like) or any(
        hint.lower() in src_blob for hint in item.must_cite_source_like
    )

    return ItemScore(
        id=item.id, scorable=True, behavior_correct=behavior_correct,
        obligation_recall=recall, missed_obligations=missed,
        citations_resolvable=citations_resolvable, unresolved_citations=unresolved,
        source_cited_ok=source_cited_ok,
    )


@dataclass
class Report:
    n_items: int
    n_scorable: int
    macro_obligation_recall: float
    behavior_accuracy: float
    citation_resolvable_rate: float
    source_cited_rate: float
    total_input_tokens: int
    total_output_tokens: int
    item_scores: list[ItemScore] = field(default_factory=list)

    # Falsifiable success thresholds (research target).
    RECALL_FLOOR = 0.99
    CITATION_FLOOR = 1.0
    BEHAVIOR_FLOOR = 1.0

    def passes(self) -> bool:
        return (
            self.macro_obligation_recall >= self.RECALL_FLOOR
            and self.citation_resolvable_rate >= self.CITATION_FLOOR
            and self.behavior_accuracy >= self.BEHAVIOR_FLOOR
        )


def aggregate(items, results, judge=None) -> Report:
    scores = [score_item(it, results[it.id], judge) for it in items]
    scorable = [s for s in scores if s.scorable]
    recall_pool = [s.obligation_recall for s in scorable]
    cite_pool = [s for s in scores if (results[s.id].text and not detect_abstention(results[s.id]))]

    def rate(predicate, pool):
        pool = list(pool)
        return sum(1 for x in pool if predicate(x)) / len(pool) if pool else 1.0

    return Report(
        n_items=len(scores),
        n_scorable=len(scorable),
        macro_obligation_recall=sum(recall_pool) / len(recall_pool) if recall_pool else 0.0,
        behavior_accuracy=rate(lambda s: s.behavior_correct, scores),
        citation_resolvable_rate=rate(lambda s: s.citations_resolvable, cite_pool),
        source_cited_rate=rate(lambda s: s.source_cited_ok, [s for s in scorable if results[s.id].sources]),
        total_input_tokens=sum(r.input_tokens for r in results.values()),
        total_output_tokens=sum(r.output_tokens for r in results.values()),
        item_scores=scores,
    )
