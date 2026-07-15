"""Cross-examination agent — one bounded round where the specialists challenge,
corroborate, or flag each other's claims BEFORE synthesis.

This is what makes the agents visibly "communicate": instead of four parallel
reports that never interact, this node reads all of them in a single grounded
LLM call and surfaces genuine cross-agent exchanges (e.g. the Competitor agent
questioning a Trend figure, or the RBI agent flagging a PESTEL legal claim).

Bounded on purpose: ONE LLM call, a handful of messages, grounded in the actual
report text — not an open-ended multi-agent loop (which would blow up latency and
Gemini quota). Fails safe: any error yields no debate rather than breaking the run.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import get_llm

_AGENTS = ["rbi", "pestel", "competitor", "trend"]
_LABEL = {"rbi": "RBI compliance", "pestel": "PESTEL", "competitor": "Competitor", "trend": "Trend"}
_KINDS = {"challenge", "corroborate", "flag"}
_MAX_MESSAGES = 7

# Plain-text line protocol parses far more reliably on flash-lite than JSON mode.
SYSTEM_PROMPT = """You moderate a real cross-examination between four FINANCIAL analysts who EACH wrote a report on the user's business question: RBI/financial-regulation (rbi), PESTEL (pestel), Competitor (competitor), and Trend (trend). They should argue like a sharp investment committee — stress-testing each other's NUMBERS and FEASIBILITY.

Surface 5-7 GENUINE cross-agent exchanges grounded in the ACTUAL report text. Make it a back-and-forth: where one agent challenges another, have the target reply in a later line if the reports support it. Each exchange uses one intent:
- challenge: stress-tests another agent's claim — a margin/CAC/funding/ROI number, a financing assumption, or whether a move survives a regulatory or cost headwind.
- corroborate: independently confirms another agent's claim from its own report.
- flag: warns a claim carries a compliance, cash-flow or freshness risk.

Output ONLY the exchanges, one per line, in EXACTLY this pipe format and nothing else:
source > target | kind | message

source and target are each one of rbi/pestel/competitor/trend (and differ); kind is challenge/corroborate/flag; message is 1-2 specific sentences naming the real claim and its number where present (keep any [S#] tags). Example:
competitor > trend | challenge | Your projected 60% gross margin on sub-premium [S2] ignores the higher fabric COGS the competitor pricing [S4] implies.

Do NOT invent facts not present in the reports. No preamble, no numbering, no markdown."""


def _parse(text: str, reports: dict) -> list:
    out = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip()
        if line.count("|") < 2 or ">" not in line.split("|")[0]:
            continue
        head, kind, msg = (p.strip() for p in line.split("|", 2))
        src, _, tgt = (p.strip().lower() for p in head.partition(">"))
        kind = kind.lower()
        if src in reports and tgt in reports and src != tgt and msg:
            out.append({
                "source": src, "target": tgt,
                "source_label": _LABEL[src], "target_label": _LABEL[tgt],
                "kind": kind if kind in _KINDS else "challenge",
                "text": msg,
            })
        if len(out) >= _MAX_MESSAGES:
            break
    return out


def crossexam_node(state: dict) -> dict:
    flags = state.get("route_flags", {})
    reports = {a: state.get(f"{a}_report", "") for a in _AGENTS
               if flags.get(a) and state.get(f"{a}_report")}
    # Need at least two reports for a conversation to exist.
    if len(reports) < 2:
        return {"cross_messages": []}

    llm = get_llm("reasoning")
    payload = "\n\n".join(f"### {_LABEL[a]} ({a}) report:\n{t}" for a, t in reports.items())
    try:
        resp = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"The reports:\n\n{payload}\n\nNow output the cross-examination lines."),
        ])
        return {"cross_messages": _parse(getattr(resp, "content", ""), reports)}
    except Exception:  # noqa: BLE001 - debate is enrichment; never break the run
        return {"cross_messages": []}
