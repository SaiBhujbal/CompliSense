"""CompliSense LangGraph workflow.

    orchestrator ──ambiguous/out-of-scope──> END (UI shows clarification)
         │ proceed
         ▼
      dispatch ──parallel──> [rbi, pestel, competitor, trend]   (each no-ops if not routed)
                                   │ fan-in
                                   ▼
                            faithfulness ──invalid & retries left──> re-run ONLY failing agent
                                   │ valid / retries exhausted
                                   ▼
                            crossexam ──(agents challenge/corroborate each other)
                                   │
                                   ▼
                              swot ──(deep financial SWOT + TOWS)
                                   │
                                   ▼
                              analysis ──> responder ──> END

Every node is wrapped so an uncaught exception degrades that leg instead of
killing Ask AI / the SSE stream.
"""

from typing import Callable, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .. import config
from ..agents import (
    analysis_node,
    competitor_node,
    crossexam_node,
    faithfulness_node,
    orchestrator_node,
    pestel_node,
    rbig_node,
    response_node,
    swot_node,
    trend_node,
)
from ..state import AgentState

_SPECIALISTS = ["rbi", "pestel", "competitor", "trend"]

_REPORT_KEYS = {
    "rbi": "rbi_report",
    "pestel": "pestel_report",
    "competitor": "competitor_report",
    "trend": "trend_report",
    "swot": "swot_report",
    "analysis": "final_analysis",
    "responder": "final_response",
}


def _safe(name: str, fn: Callable) -> Callable:
    """Never let a node exception take down the whole graph."""

    def wrapped(state: AgentState) -> dict:
        try:
            out = fn(state)
            return out if isinstance(out, dict) else {}
        except Exception as e:  # noqa: BLE001
            detail = f"{type(e).__name__}: {e}"[:200]
            key = _REPORT_KEYS.get(name)
            if key:
                return {key: f"[{name} skipped — {detail}]"}
            if name == "orchestrator":
                return {
                    "in_scope": True,
                    "is_ambiguous": True,
                    "clarification_question": (
                        "I hit an unexpected error while routing your question "
                        f"({detail}). Please try again in a moment."
                    ),
                    "analysis_lens": "finance",
                    "route_flags": {
                        "rbi": False, "pestel": False, "competitor": False, "trend": False,
                    },
                }
            if name == "faithfulness":
                return {"faithfulness_status": "valid", "failing_agent": None}
            return {}

    wrapped.__name__ = f"safe_{name}"
    return wrapped


def _dispatch(state: AgentState) -> dict:
    """No-op fan-out point; agents self-gate on route_flags."""
    return {}


def route_after_orchestration(state: AgentState) -> Literal["end", "proceed"]:
    if state.get("is_ambiguous", False) or not state.get("in_scope", True):
        return "end"
    return "proceed"


def route_after_faithfulness(state: AgentState) -> str:
    failing = state.get("failing_agent")
    if (
        state.get("faithfulness_status") == "invalid"
        and state.get("retry_count", 0) <= config.MAX_FAITHFULNESS_RETRIES
        and failing in _SPECIALISTS
    ):
        return failing
    return "crossexam"


def create_workflow():
    g = StateGraph(AgentState)

    g.add_node("orchestrator", _safe("orchestrator", orchestrator_node))
    g.add_node("dispatch", _dispatch)
    g.add_node("rbi", _safe("rbi", rbig_node))
    g.add_node("pestel", _safe("pestel", pestel_node))
    g.add_node("competitor", _safe("competitor", competitor_node))
    g.add_node("trend", _safe("trend", trend_node))
    g.add_node("faithfulness", _safe("faithfulness", faithfulness_node))
    g.add_node("crossexam", _safe("crossexam", crossexam_node))
    g.add_node("swot", _safe("swot", swot_node))
    g.add_node("analysis", _safe("analysis", analysis_node))
    g.add_node("responder", _safe("responder", response_node))

    g.set_entry_point("orchestrator")
    g.add_conditional_edges(
        "orchestrator", route_after_orchestration, {"end": END, "proceed": "dispatch"}
    )

    for agent in _SPECIALISTS:
        g.add_edge("dispatch", agent)
        g.add_edge(agent, "faithfulness")

    g.add_conditional_edges(
        "faithfulness",
        route_after_faithfulness,
        {**{a: a for a in _SPECIALISTS}, "crossexam": "crossexam"},
    )
    g.add_edge("crossexam", "swot")
    g.add_edge("swot", "analysis")
    g.add_edge("analysis", "responder")
    g.add_edge("responder", END)

    return g.compile(checkpointer=MemorySaver())
