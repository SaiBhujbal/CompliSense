from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """The state of the multi-agent system."""
    user_query: str
    messages: Annotated[List[BaseMessage], operator.add]
    
    # Orchestrator output
    is_ambiguous: bool
    clarification_question: str
    analysis_intent: str
    
    # Parallel Agent outputs
    rbi_compliance_report: str
    pestel_report: str
    competitor_report: str
    trend_report: str
    
    # Validator output
    validation_status: str # 'valid', 'invalid'
    validation_reason: str
    
    # Analysis and Final outputs
    final_analysis: str
    final_response: str