import streamlit as st
import uuid
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

# Adjust the import path based on your project structure
from src.graph.workflow import create_workflow
from src.state import AgentState

# --- Page Configuration ---
st.set_page_config(
    page_title="Compli-Sense",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 Compli-Sense: AI for FinTech Strategy")
st.caption("Your intelligent guide to RBI compliance, market analysis, and strategic decisions in the Indian FinTech ecosystem.")

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "graph" not in st.session_state:
    # Initialize the LangGraph workflow
    # Using a unique thread_id for each session
    st.session_state.graph = create_workflow()
    st.session_state.thread_id = str(uuid.uuid4())

# --- Display Chat History ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Main Chat Input ---
if prompt := st.chat_input("Ask me anything about starting a FinTech business in India..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Invoke the LangGraph workflow
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Create the initial state for the graph
        initial_state = {
            "user_query": prompt,
            "messages": [HumanMessage(content=prompt)],
        }
        
        # Run the graph
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        
        try:
            final_state = st.session_state.graph.invoke(initial_state, config)
            
            # Check if the orchestrator found the query ambiguous
            if final_state.get("is_ambiguous"):
                full_response = final_state.get("clarification_question", "I'm sorry, I need more information.")
            else:
                # Check if validation failed after max retries
                retry_count = final_state.get("retry_count", 0)
                if retry_count > 2 and final_state.get("validation_status") == "invalid":
                    full_response = (
                        "I apologize, but I'm having difficulty generating a fully validated response. "
                        "Here's what I found:\n\n"
                        f"**Validation Issue**: {final_state.get('validation_reason', 'Unknown issue')}\n\n"
                        "Please try rephrasing your question or being more specific about your requirements."
                    )
                else:
                    # Otherwise, get the final response
                    full_response = final_state.get("final_response", "I'm sorry, I couldn't process that request.")
            
            message_placeholder.markdown(full_response)

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_message = (
                f"An error occurred while processing your request. "
                f"Please check your API keys and try again.\n\n"
                f"**Error**: {str(e)}"
            )
            st.error(error_message)
            # Log full error for debugging (only visible in console)
            print(f"Error details:\n{error_details}")
            full_response = "I encountered an error. Please try again or contact support if the issue persists."

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
