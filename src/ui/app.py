"""Streamlit UI for CompliSense.

Shows the final response (which already carries a forced disclaimer), surfaces
the source citations behind each answer, and flags any faithfulness warnings.
"""

import src._bootstrap  # noqa: F401  -- init torch/ST before chromadb (must be first)

import uuid

import streamlit as st
from langchain_core.messages import HumanMessage

from src.config import validate_config
from src.graph.workflow import create_workflow

st.set_page_config(page_title="CompliSense", page_icon="🤖", layout="centered")
st.title("🤖 CompliSense — RBI Compliance & FinTech Strategy")
st.caption("Grounded, cited guidance for the Indian FinTech ecosystem.")

# Fail fast on misconfiguration with a clear message.
try:
    validate_config()
except Exception as e:  # noqa: BLE001
    st.error(f"Configuration error: {e}")
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "graph" not in st.session_state:
    st.session_state.graph = create_workflow()
    st.session_state.thread_id = str(uuid.uuid4())

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about RBI compliance or your FinTech strategy in India..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Consulting the compliance agents..."):
                final = st.session_state.graph.invoke(
                    {"user_query": prompt, "messages": [HumanMessage(content=prompt)]},
                    {"configurable": {"thread_id": st.session_state.thread_id}},
                )

            if final.get("is_ambiguous") or not final.get("in_scope", True):
                answer = final.get("clarification_question", "Could you clarify your question?")
            else:
                answer = final.get("final_response", "Sorry, I couldn't produce an answer.")

            st.markdown(answer)

            # Surface citations so claims are verifiable.
            sources = final.get("sources", {})
            flat = [(agent, s) for agent, lst in sources.items() for s in lst]
            if flat:
                with st.expander("Sources"):
                    for agent, s in flat:
                        st.markdown(f"- `[{s['id']}]` ({agent}) {s.get('title','')} — {s.get('ref','')}")

            if final.get("unsupported_claims"):
                st.warning(
                    "Some claims could not be fully verified against sources:\n\n"
                    + "\n".join(f"- {c}" for c in final["unsupported_claims"])
                )
        except Exception as e:  # noqa: BLE001
            import traceback

            print(traceback.format_exc())
            answer = "I hit an error processing that. Check API keys / vector store and try again."
            st.error(f"{answer}\n\n**Error:** {e}")

    st.session_state.messages.append({"role": "assistant", "content": answer})
