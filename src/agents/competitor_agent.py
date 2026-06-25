"""Competitor agent — bounded ReAct.

This is the one agent that genuinely needs reason->act->observe iteration: it
discovers competitors, then searches each for funding/positioning. The loop is
HARD-capped (config.COMPETITOR_MAX_SEARCHES) so it can't blow up cost. Funding
figures are cite-or-omit; every claim cites the [S#] of its source URL.
"""

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .. import config
from ..llm import get_llm
from ..llm.structured import invoke_structured
from ..tools import tavily_search

DECIDE_PROMPT = """You are a market-intelligence analyst researching competitors via web search, one search at a time.
Given the intent and findings so far, decide the next action:
- action="search" with a focused `query` if you still need data (e.g. a specific competitor's funding).
- action="final" with `report` once you have enough to name 3-5 competitors with model, products, funding, strengths/weaknesses.
Prefer to finish early; do not pad with extra searches."""

FINAL_PROMPT = """Write the competitor analysis from the findings. Name 3-5 key players; for each give business model, products, recent funding (ONLY if present in findings — else omit), and strengths/weaknesses. Cite every claim with its [S#] tag. Do NOT invent companies or figures."""


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

    for step in range(config.COMPETITOR_MAX_SEARCHES):
        decision = invoke_structured(
            llm, CompetitorStep,
            [
                SystemMessage(content=DECIDE_PROMPT),
                HumanMessage(content=f"Intent: {intent}\n\nFindings so far:\n{transcript or '(none yet)'}\n\nDecide the next action."),
            ],
            fallback=CompetitorStep(action="search", query=f"top competitors {intent} India funding"),
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

    # Cap reached — synthesize from what we gathered.
    final = llm.invoke([
        SystemMessage(content=FINAL_PROMPT),
        HumanMessage(content=f"Intent: {intent}\n\nFindings:\n{transcript}\n\nWrite the report, citing [S#]."),
    ])
    return {"competitor_report": final.content, "sources": {"competitor": all_sources}}
