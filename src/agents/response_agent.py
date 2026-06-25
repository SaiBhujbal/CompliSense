"""Response agent — user-facing answer with a NON-DISMISSIBLE disclaimer.

The disclaimer is force-appended in code (not left to the LLM) because this tool
gives regulatory guidance to non-experts — it is a product requirement, not a
stylistic choice.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from .. import config
from ..llm import get_llm

SYSTEM_PROMPT = """Present the strategic analysis to a non-expert founder clearly and concisely:
- Acknowledge their goal.
- Bullet the key opportunities, risks, and recommended next steps.
- KEEP the [S#] citation markers so claims stay traceable.
- Be supportive and easy to read; do not dump the full analysis."""


def response_node(state: dict) -> dict:
    llm = get_llm("fast")
    human = (
        f"User's question: {state['user_query']}\n\n"
        f"Strategic analysis:\n---\n{state.get('final_analysis', 'Not available.')}\n---\n\n"
        "Write the final user-facing response, keeping [S#] markers."
    )
    resp = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human)])
    # Force-append the disclaimer — cannot be omitted by the model.
    return {"final_response": f"{resp.content}\n\n---\n{config.DISCLAIMER}"}
