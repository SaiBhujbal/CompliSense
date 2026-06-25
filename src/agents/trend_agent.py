"""Trend agent — single-pass, one fresh search, date-pinned.

Time-sensitive: graph/iterative over-retrieval HURTS freshness, so this is a
single shallow search + one structured pass. Predictions must be grounded in the
retrieved results and cite [S#]; the current year is pinned to avoid stale framing.
"""

from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..tools import tavily_search

SYSTEM_PROMPT = """You are a FinTech trend analyst. Based ONLY on the provided, dated search results:
1. Current trends: the most significant developments happening now.
2. Near-term outlook (next 1-2 years), grounded in the evidence — label clearly as projection.
3. Statistical signals (growth rates, adoption) IF present in the results.
4. Relevance to the user's goal.
Cite every claim with its [S#] tag. Do NOT make unsupported predictions; if evidence is thin, say so."""


def trend_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("trend"):
        return {}

    intent = state.get("analysis_intent") or state["user_query"]
    year = date.today().year
    try:
        context, sources = tavily_search(f"Indian FinTech trends {year} outlook {intent}")
    except Exception as e:  # noqa: BLE001
        return {"trend_report": f"Trend web search unavailable: {e}", "sources": {"trend": []}}

    llm = get_llm("reasoning")
    human = (
        f"User's interest: {intent}\nToday's year: {year}\n\n"
        f"Search results:\n---\n{context}\n---\n\nWrite the trend report, citing [S#] tags."
    )
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)])
    return {"trend_report": resp.content, "sources": {"trend": sources}}
