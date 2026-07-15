"""Trend agent — single-pass, one fresh search, date-pinned.

Time-sensitive: graph/iterative over-retrieval HURTS freshness, so this is a
single shallow search + one structured pass. Predictions must be grounded in the
retrieved results and cite [S#]; the current year is pinned to avoid stale framing.
"""

from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..llm.structured import safe_invoke
from ..tools import tavily_search

SYSTEM_PROMPT = """You are a FINANCIAL trend analyst at a finance & compliance copilot. For a business in the user's sector, report the FINANCIAL trends that matter — NOT product, design or marketing fads. Based ONLY on the provided, dated search results:
1. Capital & financing trends: how this sector is being funded (equity, debt, working-capital, MSME credit, revenue-based finance); the funding climate.
2. Payments & checkout-finance trends: payment rails, BNPL/EMI, settlement, and what they do to cash flow and conversion.
3. Unit-economics / margin / cost trends and pricing power in the sector.
4. Near-term outlook (next 12-18 months) — clearly labelled as projection — and what it means for the user's goal financially.
Include statistical signals (growth rates, margins, CAC, funding totals) IF present. Cite every claim with its [S#] tag. Do NOT make unsupported predictions; if evidence is thin, say so."""


def trend_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("trend"):
        return {}

    intent = state.get("analysis_intent") or state["user_query"]
    sector = state.get("sector") or "this business"
    year = date.today().year
    try:
        # Financial trends of the sector, not its style trends.
        context, sources = tavily_search(
            f"{sector} India {year}: financing and funding trends, unit economics and margins, "
            f"working capital, pricing, customer acquisition cost, payment and BNPL trends"
        )
    except Exception as e:  # noqa: BLE001
        return {"trend_report": f"Trend web search unavailable: {e}", "sources": {"trend": []}}

    llm = get_llm("reasoning")
    human = (
        f"User's sector: {sector}\nFinancial brief: {intent}\nToday's year: {year}\n\n"
        f"Search results:\n---\n{context}\n---\n\nWrite the FINANCIAL trend report, citing [S#] tags."
    )
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback="Trend financial read was rate-limited this run; rely on the other reports for now.",
    )
    return {"trend_report": content, "sources": {"trend": sources}}
