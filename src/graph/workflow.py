from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.constants import START

from ..state import AgentState
from ..agents import (
    orchestrator_node,
    rbig_node,
    pestel_node,
    competitor_node,
    trend_node,
    validator_node,
    analysis_node,
    response_node
)
from langgraph.checkpoint.memory import MemorySaver

# Define the routing logic functions
def route_after_orchestration(state: AgentState) -> Literal["clarify", "parallel_agents"]:
    if state.get("is_ambiguous", True):
        return "clarify"
    else:
        return "parallel_agents"

def route_after_validation(state: AgentState) -> Literal["parallel_agents", "analysis"]:
    if state.get("validation_status") == "invalid":
        return "parallel_agents" # Loop back for re-run
    else:
        return "analysis"

# Create the workflow graph
def create_workflow():
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("rbig_agent", rbig_node)
    workflow.add_node("pestel_agent", pestel_node)
    workflow.add_node("competitor_agent", competitor_node)
    workflow.add_node("trend_agent", trend_node)
    workflow.add_node("validator", validator_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("responder", response_node)
    
    # Set the entry point
    workflow.set_entry_point("orchestrator")
    
    # Add conditional edges from orchestrator
    workflow.add_conditional_edges(
        "orchestrator",
        route_after_orchestration,
        {
            "clarify": END, # The UI will handle displaying the clarification
            "parallel_agents": "rbig_agent" # Start the parallel chain
        }
    )
    
    # Define the parallel execution flow
    # After rbig_agent, we run the others in parallel. LangGraph handles this implicitly
    # when a node has multiple outgoing edges to different nodes that don't depend on each other.
    workflow.add_edge("rbig_agent", "pestel_agent")
    workflow.add_edge("rbig_agent", "competitor_agent")
    workflow.add_edge("rbig_agent", "trend_agent")
    
    # All parallel agents must complete before validation
    workflow.add_edge("pestel_agent", "validator")
    workflow.add_edge("competitor_agent", "validator")
    workflow.add_edge("trend_agent", "validator")
    
    # Add conditional edges from validator
    workflow.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "parallel_agents": "rbig_agent", # Re-run the parallel agents
            "analysis": "analysis"
        }
    )
    
    # Final linear steps
    workflow.add_edge("analysis", "responder")
    workflow.add_edge("responder", END)
    
    # Initialize memory to allow for state persistence across runs (optional but good practice)
    memory = MemorySaver()
    
    # Compile the graph
    app = workflow.compile(checkpointer=memory)
    return app