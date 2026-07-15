"""Shared LangGraph state for the CompliSense multi-agent workflow."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage


def _merge_dicts(a: dict, b: dict) -> dict:
    """Reducer: merge per-agent dicts written by parallel nodes (disjoint keys)."""
    return {**(a or {}), **(b or {})}


class AgentState(TypedDict, total=False):
    """State of the CompliSense graph.

    Reports and the ``sources`` map are written by parallel agents; reports use
    disjoint keys (no reducer needed), ``sources`` uses a merge reducer.
    """

    user_query: str
    messages: Annotated[list[BaseMessage], operator.add]

    # Orchestrator (scope-guard + clarify + intent routing)
    is_ambiguous: bool
    in_scope: bool
    clarification_question: str
    analysis_intent: str  # orchestrator brief for specialists (follows user lens)
    analysis_lens: str  # auto-classified: customer|finance|competitor|strategy|growth|regulatory
    sector: str  # the user's industry, e.g. "D2C apparel", "digital-lending NBFC"
    # Which specialist agents this query actually needs.
    route_flags: dict  # {"rbi": bool, "pestel": bool, "competitor": bool, "trend": bool}

    # Specialist agent reports (each embeds [S#] citation tags).
    rbi_report: str
    pestel_report: str
    competitor_report: str
    trend_report: str

    # Citation registry: agent_name -> [{"id": "S1", "title": ..., "ref": ...}]
    sources: Annotated[dict, _merge_dicts]

    # Faithfulness gate
    faithfulness_status: str  # "valid" | "invalid"
    unsupported_claims: list
    failing_agent: str
    retry_count: int

    # Cross-examination round (agents challenge/corroborate each other before synthesis)
    cross_messages: list  # [{source,target,source_label,target_label,kind,text}]

    # Deep financial SWOT (+ TOWS) synthesized from the specialist reports
    swot_report: str

    # Final outputs
    final_analysis: str
    final_response: str
