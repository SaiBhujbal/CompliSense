"""Synthesis agent — cross-agent strategic analysis, citations preserved."""

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm

SYSTEM_PROMPT = """You are a strategy consultant for Indian FinTech. Synthesize the provided reports
(some of: RBI compliance, PESTEL, competitor, trend) into one coherent analysis:
1. Connect the dots across regulation, market, and trends.
2. Opportunities.
3. Risks (regulatory risks first).
4. 2-3 concrete next steps.
5. If the query is risk- or readiness-oriented, also emit a REGULATORY-RISK REGISTER as a table:
   Risk | Likelihood (H/M/L) | Regulatory source [S#] | Mitigation — regulatory risks first, each row [S#]-cited.
PRESERVE the [S#] citation tags from the source reports when you reuse their claims. Do not invent new facts."""


def analysis_node(state: dict) -> dict:
    llm = get_llm("reasoning")
    intent = state.get("analysis_intent") or state["user_query"]
    parts = []
    for agent, label in [("rbi", "RBI Compliance"), ("pestel", "PESTEL"),
                         ("competitor", "Competitor"), ("trend", "Trend")]:
        report = state.get(f"{agent}_report")
        if report:
            parts.append(f"### {label} report:\n{report}")
    body = "\n\n".join(parts) if parts else "No specialist reports were produced."

    unsupported = state.get("unsupported_claims") or []
    caveat = (
        f"\n\nNOTE: the faithfulness check flagged these as unverified — do NOT rely on them: {unsupported}"
        if unsupported else ""
    )
    human = f"User's goal: {intent}\n\n{body}{caveat}\n\nWrite the synthesized strategic analysis."
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)])
    return {"final_analysis": resp.content}
