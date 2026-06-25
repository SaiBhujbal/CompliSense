"""Orchestrator: scope-guard + clarification + intent routing.

Single fast-model pass. Decides (a) whether the query is in scope (Indian
RBI / FinTech strategy), (b) whether it's too vague to answer, and (c) WHICH
specialist agents to actually run — so we don't pay for all four every time.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from ..llm import get_llm
from ..llm.structured import invoke_structured

SYSTEM_PROMPT = """You are the orchestrator for CompliSense, an AI copilot for the INDIAN FinTech ecosystem (RBI compliance + market strategy).

Analyze the user's query and decide:
1. in_scope: Is this about Indian FinTech / RBI regulation / starting or running a FinTech business in India? If clearly outside this (e.g. unrelated topics, other jurisdictions with no India angle, personal legal advice), set false.
2. is_ambiguous: Too vague to act on (no clear goal/sector). If so, write a specific clarification_question.
3. analysis_intent: If clear, a one-sentence summary of what the user wants to achieve.
4. Route ONLY the agents the query needs:
   - needs_rbi: RBI rules/compliance/licensing implied.
   - needs_pestel: macro-environment (political/economic/social/tech/legal) relevant.
   - needs_competitor: user cares about competitors/market players.
   - needs_trend: user cares about future/market trends.
Default to needs_rbi=true for compliance questions; enable the others only when relevant."""


class Routing(BaseModel):
    in_scope: bool = True
    is_ambiguous: bool = False
    clarification_question: str = ""
    analysis_intent: str = ""
    needs_rbi: bool = True
    needs_pestel: bool = False
    needs_competitor: bool = False
    needs_trend: bool = False


def orchestrator_node(state: dict) -> dict:
    llm = get_llm("fast")
    # Fallback: treat as an in-scope compliance question, run RBI only.
    r = invoke_structured(
        llm, Routing,
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=state["user_query"])],
        fallback=Routing(in_scope=True, is_ambiguous=False, analysis_intent=state["user_query"]),
    )

    if not r.in_scope:
        return {
            "in_scope": False, "is_ambiguous": True,
            "clarification_question": (
                "I'm focused on Indian FinTech strategy and RBI compliance. "
                "Could you rephrase your question within that scope?"
            ),
            "route_flags": {"rbi": False, "pestel": False, "competitor": False, "trend": False},
        }

    return {
        "in_scope": True,
        "is_ambiguous": r.is_ambiguous,
        "clarification_question": r.clarification_question,
        "analysis_intent": r.analysis_intent or state["user_query"],
        "route_flags": {
            "rbi": r.needs_rbi, "pestel": r.needs_pestel,
            "competitor": r.needs_competitor, "trend": r.needs_trend,
        },
    }
