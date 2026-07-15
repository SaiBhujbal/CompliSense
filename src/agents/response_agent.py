"""Response agent — user-facing answer with a NON-DISMISSIBLE disclaimer.

The disclaimer is force-appended in code (not left to the LLM) because this tool
gives regulatory guidance to non-experts — it is a product requirement, not a
stylistic choice.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm
from ..llm.structured import safe_invoke

SYSTEM_PROMPT = """Present the FINANCIAL STRATEGY to a founder clearly, in depth, and well-structured — finance is the lens. Do NOT shrink it to a generic pep-talk.
- Open with one line acknowledging their goal.
- Then deliver the substance under clear headings: the financial case for the move (with any margin / ROI / unit-economics numbers from the analysis), how to fund it (financing options + rough capital), the payments / GST / compliance setup that affects cash flow or legality, the market/competitor opening, and concrete next steps.
- KEEP every [S#] citation marker so claims stay traceable.
- Be thorough and specific — preserve the depth of the analysis; do not truncate or omit the numbers and regulatory points. Avoid generic branding/marketing advice."""


def response_node(state: dict) -> dict:
    llm = get_llm("reasoning")
    human = (
        f"User's question: {state['user_query']}\n\n"
        f"Strategic analysis:\n---\n{state.get('final_analysis', 'Not available.')}\n---\n\n"
        "Write the final user-facing response, keeping [S#] markers."
    )
    analysis = state.get("final_analysis", "Not available.")
    content = safe_invoke(
        llm, [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)],
        fallback=analysis,  # if the model is busy, show the full analysis rather than nothing
    )
    # Force-append the disclaimer — cannot be omitted by the model.
    return {"final_response": f"{content}\n\n---\n{config.DISCLAIMER}"}
