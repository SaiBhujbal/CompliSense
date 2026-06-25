"""Run RBI-NormBench.

  python -m evals.run_eval --mock     # no API keys/corpus needed (self-check)
  python -m evals.run_eval            # runs the real CompliSense pipeline
  python -m evals.run_eval --judge    # use an LLM judge for fuzzy obligation match

The --mock path uses canned answers (one with a missed obligation and a
fabricated citation) so you can confirm the harness DISCRIMINATES before
trusting it on the real system.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import Report, aggregate
from .schema import AnswerResult, BenchItem

DATASET = Path(__file__).parent / "dataset" / "rbi_normbench.jsonl"


def load_items() -> list[BenchItem]:
    items = []
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(BenchItem.from_dict(json.loads(line)))
    return items


# --------------------------------------------------------------------------- #
# Mock answers — intentionally imperfect to prove the harness catches problems.
# --------------------------------------------------------------------------- #
def mock_answers(items: list[BenchItem]) -> dict[str, AnswerResult]:
    """Canned answers for the self-check. One item is deliberately FLAWED
    (missed obligation + fabricated citation); the rest are auto-generated as
    correct, so the run shows the harness discriminating."""
    # The deliberately-flawed item: surfaces 26% but MISSES the 30% rule, and
    # cites a NON-EXISTENT [S2] -> must fail recall AND citation resolvability.
    flawed = {
        "rbi-cc-001": AnswerResult(
            text="Yes. A change in shareholding of 26% or more needs prior RBI approval [S1]. [S2]",
            sources=[{"id": "S1", "title": "Scale Based Regulation - change in control", "ref": "rbi sbr"}],
            input_tokens=1200, output_tokens=90,
        ),
    }
    out: dict[str, AnswerResult] = {}
    for it in items:
        if it.id in flawed:
            out[it.id] = flawed[it.id]
        elif it.expected_behavior == "abstain":
            out[it.id] = AnswerResult(
                text="I could not find a relevant RBI source; this is out of scope.",
                sources=[], input_tokens=300, output_tokens=30, abstained=True,
            )
        else:
            facts = [kf for ob in it.required_obligations for kf in ob.key_facts]
            title = it.must_cite_source_like[0] if it.must_cite_source_like else "RBI"
            body = "; ".join(facts) if facts else "see the relevant directions"
            out[it.id] = AnswerResult(
                text=f"Per the RBI directions: {body} [S1].",
                sources=[{"id": "S1", "title": title, "ref": title}],
                input_tokens=1000, output_tokens=60,
            )
    return out


def pipeline_answers(items: list[BenchItem]) -> dict[str, AnswerResult]:
    """Run the real CompliSense graph (needs API keys + ingested corpus)."""
    from src.graph.workflow import create_workflow
    from langchain_core.messages import HumanMessage

    graph = create_workflow()
    out: dict[str, AnswerResult] = {}
    for it in items:
        state = graph.invoke(
            {"user_query": it.question, "messages": [HumanMessage(content=it.question)]},
            {"configurable": {"thread_id": f"eval-{it.id}"}},
        )
        ambiguous = state.get("is_ambiguous") or not state.get("in_scope", True)
        text = (
            state.get("clarification_question", "")
            if ambiguous
            else state.get("final_response") or state.get("rbi_report", "")
        )
        sources = [s for lst in state.get("sources", {}).values() for s in lst]
        out[it.id] = AnswerResult(
            text=text,
            sources=sources,
            input_tokens=len(it.question) // 4,   # rough; replace with usage metadata
            output_tokens=len(text) // 4,
            abstained=ambiguous,
        )
    return out


def make_judge():
    """Optional LLM judge for fuzzy obligation matching."""
    from src.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm("reasoning")

    def judge(obligation_summary: str, answer_text: str) -> bool:
        msg = [
            SystemMessage(content="Answer only 'YES' or 'NO'."),
            HumanMessage(content=f"Does this answer clearly state the obligation?\n\nObligation: {obligation_summary}\n\nAnswer:\n{answer_text}"),
        ]
        return "yes" in llm.invoke(msg).content.strip().lower()[:5]

    return judge


def print_report(rep: Report) -> None:
    print("\n" + "=" * 60)
    print("  RBI-NormBench Report")
    print("=" * 60)
    print(f"  items: {rep.n_items}   scorable: {rep.n_scorable}")
    print(f"  normative-obligation recall (macro): {rep.macro_obligation_recall:.3f}  (floor {rep.RECALL_FLOOR})")
    print(f"  behavior accuracy (answer/abstain):  {rep.behavior_accuracy:.3f}  (floor {rep.BEHAVIOR_FLOOR})")
    print(f"  citation resolvable rate:            {rep.citation_resolvable_rate:.3f}  (floor {rep.CITATION_FLOOR})")
    print(f"  source-cited-correctly rate:         {rep.source_cited_rate:.3f}")
    print(f"  tokens: in={rep.total_input_tokens}  out={rep.total_output_tokens}")
    print("-" * 60)
    for s in rep.item_scores:
        flags = []
        if not s.behavior_correct:
            flags.append("WRONG-BEHAVIOR")
        if s.missed_obligations:
            flags.append(f"MISSED={s.missed_obligations}")
        if s.unresolved_citations:
            flags.append(f"FABRICATED-CITES={s.unresolved_citations}")
        if not s.source_cited_ok:
            flags.append("BAD-SOURCE")
        tag = "ok" if not flags else " ".join(flags)
        scor = "" if s.scorable else " (unscored: expert-label pending)"
        print(f"  {s.id:<14} recall={s.obligation_recall:.2f}  {tag}{scor}")
    print("=" * 60)
    print(f"  RESULT: {'PASS' if rep.passes() else 'FAIL'} vs research thresholds")
    print("=" * 60 + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="use canned answers (no API/corpus)")
    ap.add_argument("--judge", action="store_true", help="use an LLM judge for fuzzy obligation match")
    args = ap.parse_args()

    items = load_items()
    results = mock_answers(items) if args.mock else pipeline_answers(items)
    judge = make_judge() if args.judge else None
    print_report(aggregate(items, results, judge))


if __name__ == "__main__":
    main()
