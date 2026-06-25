"""PESTEL agent — single-pass, 6-factor structured macro-environment scan.

Structured decomposition (not subagents): one grounded pass covering all six
factors with their sub-factors (per the PESTEL framework). Grounded on the
specific Tavily source URLs it retrieves; every claim cites a [S#] tag.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..tools import tavily_search

SYSTEM_PROMPT = """You are a macro-environment analyst. Produce a PESTEL analysis for the Indian FinTech context, grounded ONLY in the provided search results.

Cover all six factors, each with its sub-factors:
- Political: government stability, policy/tariffs, tax & labour rules, trade agreements.
- Economic: interest rates, inflation, GDP/growth, disposable income, credit access, exchange rates.
- Social: demographics (e.g. ageing, wealth distribution), lifestyle/trend shifts, education, culture.
- Technological: innovations, pace of change/obsolescence, digital platforms, cybersecurity.
- Environmental: waste/energy regulation, climate impacts, public sustainability attitudes.
- Legal: employment, competition/antitrust, product & safety, IP, data protection (and how these sit ALONGSIDE RBI rules).

Rules:
- Cite every claim with the [S#] tag of the source it came from.
- If a factor has no supporting evidence in the results, write "Insufficient data found." — do NOT invent.
- This is an EXTERNAL macro scan (complements internal SWOT); stay factual and dated."""


def pestel_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("pestel"):
        return {}

    intent = state.get("analysis_intent") or state["user_query"]
    try:
        context, sources = tavily_search(
            f"PESTEL macro-environment Indian FinTech sector {intent}",
            include_domains=config.PESTEL_DOMAINS,
        )
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        return {"pestel_report": f"PESTEL web search unavailable: {e}", "sources": {"pestel": []}}

    llm = get_llm("reasoning")
    human = (
        f"User's interest: {intent}\n\nSearch results:\n---\n{context}\n---\n\n"
        "Produce the six-factor PESTEL report, citing [S#] tags."
    )
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)])
    return {"pestel_report": resp.content, "sources": {"pestel": sources}}
