"""Competitor agent — bounded ReAct.

This is the one agent that genuinely needs reason->act->observe iteration: it
discovers competitors, then searches each for funding/positioning. The loop is
HARD-capped (config.COMPETITOR_MAX_SEARCHES) and wall-clock budgeted so a slow
provider cannot stall the whole Ask AI SSE stream. Funding figures are
cite-or-omit; every claim cites the [S#] of its source URL.
"""

import time
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .. import config
from ..llm import get_llm
from ..llm.structured import invoke_structured, safe_invoke
from ..tools import tavily_search

DECIDE_PROMPT = """You are a FINANCIAL market-intelligence analyst researching competitors via web search, one search at a time. You care about each rival's MONEY posture — how they are funded, their unit economics, pricing/margin strategy, and where the financial gap is.
Given the intent and findings so far, decide the next action:
- action="search" with a focused `query` if you still need data (e.g. a specific competitor's funding round, valuation, pricing tier, or margins).
- action="final" with `report` once you can name 3-5 competitors with their funding/valuation, business & pricing model, and financial strengths/weaknesses.
Prefer to finish early; do not pad with extra searches."""

FINAL_PROMPT = """Write the competitor analysis from the findings, through a FINANCIAL lens. Name 3-5 key players; for each give: funding raised / valuation (ONLY if present in findings — else omit), business & pricing model, unit-economics or margin signals if any, and financial strengths/weaknesses. Then state WHERE THE FINANCIAL GAP / OPENING is (an underserved price tier, a margin or capital advantage the user could exploit). Cite every claim with its [S#] tag. Do NOT invent companies or figures."""


class CompetitorStep(BaseModel):
    action: Literal["search", "final"]
    query: str = ""
    report: str = ""


def competitor_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("competitor"):
        return {}

    llm = get_llm("reasoning")
    intent = state.get("analysis_intent") or state["user_query"]
    all_sources, transcript, next_id = [], "", 1
    # Wall-clock budget: Gemini retries + multi-step ReAct can otherwise stall
    # Ask AI past client timeouts with no `done` event.
    deadline = time.monotonic() + float(getattr(config, "COMPETITOR_BUDGET_SECONDS", 120))

    for step in range(config.COMPETITOR_MAX_SEARCHES):
        if time.monotonic() >= deadline:
            break
        decision = invoke_structured(
            llm, CompetitorStep,
            [
                SystemMessage(content=DECIDE_PROMPT),
                HumanMessage(content=f"Intent: {intent}\n\nFindings so far:\n{transcript or '(none yet)'}\n\nDecide the next action."),
            ],
            fallback=CompetitorStep(action="search", query=f"{state.get('sector') or intent} India top brands funding valuation pricing unit economics"),
        )

        if decision.action == "final" and step > 0:
            return {"competitor_report": decision.report or "(insufficient competitor data)",
                    "sources": {"competitor": all_sources}}

        query = decision.query or f"competitors for {intent} in India funding news"
        try:
            ctx, srcs = tavily_search(query, include_domains=config.COMPETITOR_DOMAINS, start_index=next_id)
        except Exception as e:  # noqa: BLE001
            return {"competitor_report": f"Competitor search unavailable: {e}",
                    "sources": {"competitor": all_sources}}
        next_id += len(srcs)
        all_sources += srcs
        transcript += f"\n[Search: {query}]\n{ctx}\n"

    if not transcript.strip():
        return {
            "competitor_report": (
                "Competitor research hit the time budget before any search completed. "
                "Try again, or narrow to one named rival."
            ),
            "sources": {"competitor": all_sources},
        }

    # Cap / budget reached — synthesize from what we gathered.
    final = safe_invoke(
        llm,
        [SystemMessage(content=FINAL_PROMPT),
         HumanMessage(content=f"Intent: {intent}\n\nFindings:\n{transcript}\n\nWrite the report, citing [S#].")],
        fallback="Competitor financial read was rate-limited this run; rely on the other reports for now.",
    )
    return {"competitor_report": final, "sources": {"competitor": all_sources}}
