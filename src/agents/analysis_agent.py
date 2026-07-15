"""Synthesis agent — cross-agent strategic analysis, citations preserved."""

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..llm.structured import safe_invoke

SYSTEM_PROMPT = """You are a FINANCIAL STRATEGY consultant. The user runs a business in some sector; finance is your lens. Using the provided reports (some of: RBI/financial-regulation, PESTEL, competitor, trend), answer the user's ACTUAL question as a concrete FINANCIAL STRATEGY — never generic marketing/branding advice. Structure it:
1. DIRECT ANSWER to their goal, framed financially — e.g. the unit-economics / margin / ROI case for the move, with the math where the reports give numbers (contribution margin, CAC, payback, capital at risk).
2. HOW TO FUND IT — the realistic financing options (working-capital, inventory/PO finance, MSME credit, equity) and a rough sense of capital needed.
3. PAYMENTS / TAX / COMPLIANCE that affect cash flow, pricing or legality (Payment Aggregator settlement, GST, lending/BNPL rules) — regulatory points first, each [S#]-cited.
4. THE MARKET / COMPETITOR OPENING — where the financial gap is and how to take it.
5. 3-5 CONCRETE NEXT STEPS with a financial rationale each.
Be specific and DEEP — do not truncate. Every recommendation must have a financial or regulatory reason. PRESERVE the [S#] citation tags; do not invent facts."""


def analysis_node(state: dict) -> dict:
    llm = get_llm("reasoning")
    intent = state.get("analysis_intent") or state["user_query"]
    parts = []
    for agent, label in [("rbi", "RBI Compliance"), ("pestel", "PESTEL"),
                         ("competitor", "Competitor"), ("trend", "Trend")]:
        report = state.get(f"{agent}_report")
        if report:
            parts.append(f"### {label} report:\n{report}")
    swot = state.get("swot_report")
    if swot:
        parts.append(f"### Financial SWOT + TOWS:\n{swot}")
    body = "\n\n".join(parts) if parts else "No specialist reports were produced."

    # Cross-examination exchanges (agents challenged/corroborated each other) — let
    # the synthesis reflect where claims were stress-tested or independently confirmed.
    cross = state.get("cross_messages") or []
    debate = ""
    if cross:
        lines = "\n".join(
            f"- {m['source_label']} {m['kind']}s {m['target_label']}: {m['text']}" for m in cross
        )
        debate = (
            "\n\n### Cross-examination among the agents:\n" + lines +
            "\n\nWhere a claim was challenged or flagged, weight it accordingly; "
            "where it was corroborated, you may state it with more confidence."
        )

    unsupported = state.get("unsupported_claims") or []
    # Internal guidance only — never tell the user the sources are unreliable; just
    # silently omit/caveat these specific claims.
    caveat = (
        "\n\n[Internal note — do NOT mention to the user, do NOT call the sources "
        f"unreliable: silently omit or soft-caveat only these specific claims: {unsupported}]"
        if unsupported else ""
    )
    sector = state.get("sector") or "(unspecified sector)"
    human = (f"User's sector: {sector}\nFinancial brief: {intent}\n\n{body}{debate}{caveat}\n\n"
             "Write the deep, specific FINANCIAL strategy answering their question.")
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback=body,  # degrade to the raw specialist reports rather than nothing
    )
    return {"final_analysis": content}
