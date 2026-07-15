"""Orchestrator: scope-guard + clarification + intent routing.

Single fast-model pass. Decides (a) whether the query is in scope (business /
strategy / market / compliance), (b) whether it's too vague to answer, and
(c) WHICH specialist agents to actually run — so we don't pay for all four
every time. Also auto-classifies the analysis lens from the question.
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from .. import config
from ..llm import get_llm
from ..llm.structured import invoke_structured

SYSTEM_PROMPT = """You are the orchestrator for CompliSense, a competitive, market & compliance intelligence copilot for businesses in ANY sector (apparel, SaaS, electronics, food, beauty, lending, manufacturing…). You do NOT force every question into a finance or regulatory frame — you answer the question the user actually asked, through whichever lens fits, and you route to ONLY the specialist agents that question needs.

If the user's message already states an analysis lens or framing (e.g. "through the customer lens", "regulatory lens", "competitor lens"), respect it and brief the agents accordingly. Lenses describe HOW to analyse — they do NOT mean every specialist must run.

Given the user's query, decide:
1. in_scope: true if this is ANY business / commercial / strategic / market / competitive / operational / regulatory question for an organisation or founder (any sector). false ONLY for clearly non-business requests (e.g. "write me a poem", personal trivia).
2. sector: the user's industry in a few words (e.g. "D2C apparel — oversized t-shirts", "beauty & personal care", "digital-lending NBFC", "B2B SaaS").
3. analysis_brief: REWRITE the user's question as the concrete brief the specialist agents must answer — specific to their sector AND their actual goal, never generic. Include a financial/unit-economics angle ONLY when it is genuinely relevant to the question; do not bolt it on when the user is asking about product weaknesses or customer sentiment.
4. analysis_lens: ONE of: customer | finance | competitor | strategy | growth | regulatory — the primary framing that best fits the question (auto-detect; do not ask the user to pick).
5. is_ambiguous: true only if there is genuinely no actionable business goal; then write a specific clarification_question.

Routing flags — default OFF. Set true ONLY when that specialist is actually needed for THIS question:
  - needs_rbi: true ONLY when Indian RBI / NBFC / payments-bank / digital-lending / KYC / licence / circular / compliance obligations are material to answering. Beauty, apparel, FMCG, SaaS, electronics questions about competitors, reviews, or openings → needs_rbi = false unless the user explicitly asks about regulation.
  - needs_pestel: true when macro forces (political/economic/social/tech/legal/environmental) matter to the answer.
  - needs_competitor: true when the question is about rivals, market position, openings, head-to-head, or "vs" a named competitor.
  - needs_trend: true when trajectory / 12–18 month outlook is relevant.

Examples:
- "Which competitor weakness is the most defensible opening for me?" (beauty brand vs Himalaya, customer/review framing) → lens=competitor (or customer), needs_rbi=false, needs_competitor=true, needs_pestel=true or needs_trend=true if useful, never force RBI.
- "Do I need RBI approval for a 28% investor stake?" → lens=regulatory, needs_rbi=true.
- "PESTEL for my payment-aggregator startup" → lens=growth, needs_pestel=true, needs_rbi=true (payments), needs_trend=true."""


class Routing(BaseModel):
    in_scope: bool = True
    is_ambiguous: bool = False
    clarification_question: str = ""
    sector: str = ""
    analysis_brief: str = ""
    analysis_lens: str = "finance"
    # Defaults OFF — matches the prompt. Structured-output fallbacks that omit
    # fields must not light every specialist.
    needs_rbi: bool = False
    needs_pestel: bool = False
    needs_competitor: bool = False
    needs_trend: bool = False


_VALID_LENSES = {"customer", "finance", "competitor", "strategy", "growth", "regulatory"}

# Deterministic safety net when structured output fails or the fast model
# under-routes. Explicit opt-outs ("no RBI") win.
_RBI_OPT_OUT = re.compile(
    r"\b(?:no|without|skip|not(?:\s+about)?)\s+rbi\b|\brbi\s+not\s+needed\b",
    re.I,
)
_RBI_HINTS = re.compile(
    r"\b(?:"
    r"rbi|nbfc|kyc|fema|ppi|upi|"
    r"payment[\s-]?aggregator|account[\s-]?aggregator|"
    r"digital[\s-]?lend(?:ing|er)?|co[\s-]?lend|"
    r"circular|licence|license|"
    r"reserve\s+bank|foreign\s+investor|fdi|"
    r"regulatory|compliance\s+obligation"
    r")\b",
    re.I,
)


def _regulatory_hint(query: str) -> bool:
    q = query or ""
    if _RBI_OPT_OUT.search(q):
        return False
    return bool(_RBI_HINTS.search(q))


def _fallback_routing(query: str) -> Routing:
    """Used when structured output fails — must not drop clear RBI questions."""
    reg = _regulatory_hint(query)
    return Routing(
        in_scope=True,
        analysis_brief=query,
        sector="(unspecified)",
        analysis_lens="regulatory" if reg else "finance",
        needs_rbi=reg,
        needs_pestel=True,
        needs_competitor=not reg,
        needs_trend=True,
    )


def orchestrator_node(state: dict) -> dict:
    llm = get_llm("fast")
    query = state["user_query"]
    # Build the analysis brief the specialists answer. We do NOT force a finance
    # frame — the brief follows the user's actual question and lens; routing runs
    # only the agents that question needs (unless showcase mode overrides).
    r = invoke_structured(
        llm, Routing,
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=query)],
        fallback=_fallback_routing(query),
    )

    if not r.in_scope:
        return {
            "in_scope": False, "is_ambiguous": True,
            "clarification_question": (
                "I'm a business intelligence copilot — I help with the competitive, "
                "market, strategy and compliance side of running a business in any "
                "sector. Could you ask about that aspect of your venture?"
            ),
            "analysis_lens": "finance",
            "route_flags": {"rbi": False, "pestel": False, "competitor": False, "trend": False},
        }

    # Safety net: never skip RBI when the query clearly asks about Indian
    # financial regulation (covers LLM under-routing + structured-output misses).
    if _regulatory_hint(query):
        r.needs_rbi = True
        if (r.analysis_lens or "").strip().lower() in ("", "finance"):
            r.analysis_lens = "regulatory"

    lens = (r.analysis_lens or "finance").strip().lower()
    if lens not in _VALID_LENSES:
        lens = "finance"

    showcase = config.SHOWCASE_ALL_AGENTS
    return {
        "in_scope": True,
        "is_ambiguous": r.is_ambiguous,
        "clarification_question": r.clarification_question,
        "sector": r.sector or "(unspecified)",
        "analysis_intent": r.analysis_brief or query,
        "analysis_lens": lens,
        "route_flags": {
            "rbi": True if showcase else bool(r.needs_rbi),
            "pestel": True if showcase else bool(r.needs_pestel),
            "competitor": True if showcase else bool(r.needs_competitor),
            "trend": True if showcase else bool(r.needs_trend),
        },
    }
