"""Faithfulness gate — grounded claim->source verification (replaces validator).

Two checks, both grounded (not "does this look hallucinated?"):
1. Deterministic: every [S#] cited in a report must resolve to a real source the
   agent actually retrieved (catches fabricated citations).
2. LLM grounding: flag substantive claims not supported by the cited sources.

On failure it names the single worst agent so the graph re-runs only that one.
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from ..llm import get_llm
from ..llm.structured import invoke_structured

_AGENTS = ["rbi", "pestel", "competitor", "trend"]

SYSTEM_PROMPT = """You verify that analytical reports are GROUNDED in their cited sources.
You are given reports (each with [S#] citation tags) and the list of available sources per agent.
Flag any substantive claim NOT supported by the cited sources, and name the single weakest report.
Be strict for regulatory (RBI) claims. Do not reward confident prose; reward traceability."""


class FaithfulnessVerdict(BaseModel):
    grounded: bool = True
    unsupported_claims: list[str] = Field(default_factory=list)
    worst_agent: str = ""


def faithfulness_node(state: dict) -> dict:
    flags = state.get("route_flags", {})
    sources = state.get("sources", {})
    reports = {a: state.get(f"{a}_report", "") for a in _AGENTS if flags.get(a) and state.get(f"{a}_report")}
    retry = state.get("retry_count", 0)

    # 1. Deterministic citation resolution.
    dangling = {}
    for agent, text in reports.items():
        valid_ids = {s["id"] for s in sources.get(agent, [])}
        cited = set(re.findall(r"\[(S\d+)\]", text))
        missing = cited - valid_ids
        if missing:
            dangling[agent] = sorted(missing)

    # 2. LLM grounding check.
    llm = get_llm("reasoning")
    payload = "\n\n".join(
        f"### {a.upper()} report:\n{t}\n\nAvailable sources for {a}: "
        f"{[s['id'] for s in sources.get(a, [])]}"
        for a, t in reports.items()
    )
    # Fail CLOSED: if verification can't run, treat output as unverified, not valid.
    verdict = invoke_structured(
        llm, FaithfulnessVerdict,
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=payload or "No reports to verify.")],
        fallback=FaithfulnessVerdict(
            grounded=False,
            unsupported_claims=["faithfulness verification unavailable (structured-output failure)"],
        ),
    )

    invalid = bool(dangling) or not verdict.grounded
    failing = next(iter(dangling), "") or verdict.worst_agent
    unsupported = (
        [f"{a}: fabricated citation(s) {ids}" for a, ids in dangling.items()]
        + list(verdict.unsupported_claims)
    )
    return {
        "faithfulness_status": "invalid" if invalid else "valid",
        "unsupported_claims": unsupported,
        "failing_agent": failing if failing in reports else "",
        "retry_count": retry + (1 if invalid else 0),
    }
