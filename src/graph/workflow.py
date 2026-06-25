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
                              analysis ──> responder ──> END
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .. import config
from ..agents import (
    analysis_node,
    competitor_node,
    faithfulness_node,
    orchestrator_node,
    pestel_node,
    rbig_node,
    response_node,
    trend_node,
)
from ..state import AgentState

_SPECIALISTS = ["rbi", "pestel", "competitor", "trend"]


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
        return failing  # re-run only the weak agent
    return "analysis"


def create_workflow():
    g = StateGraph(AgentState)

    g.add_node("orchestrator", orchestrator_node)
    g.add_node("dispatch", _dispatch)
    g.add_node("rbi", rbig_node)
    g.add_node("pestel", pestel_node)
    g.add_node("competitor", competitor_node)
    g.add_node("trend", trend_node)
    g.add_node("faithfulness", faithfulness_node)
    g.add_node("analysis", analysis_node)
    g.add_node("responder", response_node)

    g.set_entry_point("orchestrator")
    g.add_conditional_edges(
        "orchestrator", route_after_orchestration, {"end": END, "proceed": "dispatch"}
    )

    # Parallel fan-out / fan-in.
    for agent in _SPECIALISTS:
        g.add_edge("dispatch", agent)
        g.add_edge(agent, "faithfulness")

    g.add_conditional_edges(
        "faithfulness",
        route_after_faithfulness,
        {**{a: a for a in _SPECIALISTS}, "analysis": "analysis"},
    )
    g.add_edge("analysis", "responder")
    g.add_edge("responder", END)

    return g.compile(checkpointer=MemorySaver())
