"""SWOT agent — a DEEP, financial-lens SWOT for the user's business in ANY sector.

There is no static "SWOT": this node reads the user's description plus every
specialist report (RBI/financial-regulation, PESTEL, competitor, trend) and
produces a rigorous SWOT where every point is a FINANCIAL / capital / unit-
economics / payments / regulatory factor — then crosses them into TOWS moves.
Runs after the cross-examination so it can use the contested/corroborated claims.
Fails safe: any LLM error degrades to a short note rather than crashing the run.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm
from ..llm.structured import safe_invoke

_AGENTS = [("rbi", "RBI / financial-regulation"), ("pestel", "PESTEL"),
           ("competitor", "Competitor"), ("trend", "Trend")]

SYSTEM_PROMPT = """You are a FINANCIAL strategy analyst producing a DEEP SWOT for the user's business — finance is the lens, whatever their sector. Use the user's description and the provided specialist reports. EVERY point must be a financial, capital, unit-economics, margin, payments or regulatory factor — never generic branding/marketing/product commentary.

Produce, with real depth and specificity:

**Strengths** — 3-5 internal financial / operational advantages, each with WHY it matters in money terms (margin, capital efficiency, cash conversion, moat).
**Weaknesses** — 3-5 internal financial gaps / risks (thin margins, capital intensity, high CAC, concentration, working-capital drag), each with its financial consequence.
**Opportunities** — 3-5 external openings (from market / trend / competitor / policy) that improve capital access, margin, ROI or growth — [S#]-cite where drawn from a report.
**Threats** — 3-5 external financial / regulatory / competitive risks — [S#]-cite where drawn from a report.

Then **TOWS — strategic moves** (one each):
- SO: use a strength to seize an opportunity.
- WO: fix a weakness to unlock an opportunity.
- ST: use a strength to blunt a threat.
- WT: defend a weakness against a threat.
Each TOWS move is a CONCRETE financial action (with the number or threshold where the reports give one).

Quantify wherever the reports provide figures (margins, CAC, payback, funding, NOF/threshold). Preserve [S#] tags. Where the user's internal numbers are unknown, infer typical sector benchmarks and clearly label them as assumptions. Be the deepest, most useful read in the whole report."""


def swot_node(state: dict) -> dict:
    intent = state.get("analysis_intent") or state["user_query"]
    sector = state.get("sector") or "(unspecified sector)"
    parts = []
    for agent, label in _AGENTS:
        report = state.get(f"{agent}_report")
        if report:
            parts.append(f"### {label} report:\n{report}")
    body = "\n\n".join(parts) if parts else "No specialist reports were produced."

    cross = state.get("cross_messages") or []
    debate = ""
    if cross:
        debate = "\n\n### Where the analysts contested each other:\n" + "\n".join(
            f"- {m['source_label']} {m['kind']}s {m['target_label']}: {m['text']}" for m in cross
        )

    llm = get_llm("reasoning")
    human = (f"User's sector: {sector}\nUser's question / financial brief: {intent}\n\n"
             f"{body}{debate}\n\nProduce the deep financial SWOT + TOWS moves.")
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback="SWOT read was rate-limited this run; rely on the synthesis and the specialist reports.",
    )
    return {"swot_report": content}
