import json
from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def orchestrator_node(state: dict) -> dict:
    """
    Analyzes the user's query to determine intent and check for ambiguity.
    """
    llm = get_llm("llama3-8b-8192") # Use a faster model for routing
    system_prompt = """
    You are an expert orchestrator for a FinTech AI system. Your task is to analyze a user's query and determine if it is clear enough to be processed by specialized agents.
    
    1.  **Identify Ambiguity**: If the query is vague, lacks context, or could be interpreted in multiple ways, it is ambiguous.
    2.  **Formulate Clarification**: If ambiguous, create a specific, helpful question to ask the user to clarify their intent.
    3.  **Extract Intent**: If the query is clear, summarize the user's core intent. What do they want to achieve? (e.g., "start a digital lending NBFC", "understand risks for a payment gateway", "analyze the competitive landscape for robo-advisory").
    
    You must respond with a JSON object only. No other text.
    
    The JSON object must have the following keys:
    - "is_ambiguous": boolean (true or false)
    - "clarification_question": string (If is_ambiguous is true, provide the question. Otherwise, provide an empty string "")
    - "analysis_intent": string (If is_ambiguous is false, provide the summarized intent. Otherwise, provide an empty string "")
    
    Example for an ambiguous query: "tell me about finance"
    {
        "is_ambiguous": true,
        "clarification_question": "Could you please specify? Are you interested in starting a FinTech business, understanding recent regulations, or analyzing market trends?",
        "analysis_intent": ""
    }
    
    Example for a clear query: "I want to start a P2P lending platform in India. What are the RBI compliance requirements and who are my competitors?"
    {
        "is_ambiguous": false,
        "clarification_question": "",
        "analysis_intent": "Understand RBI compliance and analyze competitors for starting a P2P lending platform in India."
    }
    """
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state['user_query'])]
    response = llm.invoke(messages)
    
    try:
        content = json.loads(response.content)
        return {
            "is_ambiguous": content.get("is_ambiguous", True),
            "clarification_question": content.get("clarification_question", "I'm sorry, I didn't understand. Could you please rephrase?"),
            "analysis_intent": content.get("analysis_intent", "")
        }
    except json.JSONDecodeError:
        # Fallback in case LLM doesn't return valid JSON
        return {
            "is_ambiguous": True,
            "clarification_question": "I'm having trouble understanding your request. Could you please provide more details?",
            "analysis_intent": ""
        }