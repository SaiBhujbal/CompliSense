"""PESTEL agent — single-pass, 6-factor structured macro-environment scan.

Structured decomposition (not subagents): one grounded pass covering all six
factors with their sub-factors (per the PESTEL framework). Grounded on the
specific Tavily source URLs it retrieves; every claim cites a [S#] tag.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..llm.structured import safe_invoke
from ..tools import tavily_search

SYSTEM_PROMPT = """You are a FINANCIAL macro-environment analyst at a finance & compliance copilot. The user runs a business in a given sector. Produce the DEEPEST, most useful PESTEL of the forces that shape the FINANCING, CAPITAL, COSTS, PAYMENTS, TAX and FINANCIAL REGULATION of this kind of business in India — NOT generic industry, design or marketing commentary. Grounded ONLY in the provided search results.

For EACH of the six factors, give: (a) 2-3 specific SUB-FACTORS with the number/figure where the evidence has one (rates, costs, schemes, thresholds), and (b) a one-line **Financial implication for the user** — what it does to their capital, margins, cash flow or compliance.
- Political: government schemes / subsidies / credit guarantees (e.g. MSME, PLI), sector financial policy, incentives.
- Economic: capital & credit availability, interest rates, input-cost inflation, demand / disposable income, margins, funding climate.
- Social: the spending & credit behaviour of the target customer (sets pricing power and financing need).
- Technological: payment rails, lending / underwriting tech, financial automation relevant to the business.
- Environmental: cost or regulatory pressures with a real FINANCIAL impact (sustainable-sourcing cost, compliance cost).
- Legal: the financial-regulatory surface — payments (RBI Payment Aggregator), lending / BNPL, GST / tax, MSME, data protection.

End with a **Net financial read**: the 2-3 forces that most move this business's capital, margins or compliance, and why.

Rules:
- Cite every claim with the [S#] tag of its source.
- If a factor has no supporting evidence, write "Insufficient data found." — do NOT invent.
- Stay FINANCIAL, specific to the user's sector, and DEEP — this is the external macro read that feeds the SWOT."""


def pestel_node(state: dict) -> dict:
    if not state.get("route_flags", {}).get("pestel"):
        return {}

    intent = state.get("analysis_intent") or state["user_query"]
    sector = state.get("sector") or "this business"
    try:
        # Search the FINANCIAL environment of the sector, not its design/marketing trends.
        context, sources = tavily_search(
            f"{sector} in India: financing and capital access, interest rates, MSME schemes, "
            f"input-cost inflation, margins, payment regulation, GST and financial-compliance environment",
            include_domains=config.PESTEL_DOMAINS,
        )
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        return {"pestel_report": f"PESTEL web search unavailable: {e}", "sources": {"pestel": []}}

    llm = get_llm("reasoning")
    human = (
        f"User's sector: {sector}\nFinancial brief: {intent}\n\nSearch results:\n---\n{context}\n---\n\n"
        "Produce the six-factor PESTEL, read entirely through the financial lens, citing [S#] tags."
    )
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback="PESTEL financial read was rate-limited this run; rely on the other reports for now.",
    )
    return {"pestel_report": content, "sources": {"pestel": sources}}
