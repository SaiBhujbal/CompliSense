from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def response_node(state: dict) -> dict:
    """
    Converts the detailed analysis into a concise, conversational, and user-friendly response.
    """
    llm = get_llm()
    
    system_prompt = """
    You are a helpful and friendly AI assistant. Your task is to take a complex strategic analysis and present it to the user in a simple, clear, and conversational manner.
    
    The user is not necessarily an expert in finance or technology, so avoid jargon.
    
    Your response should:
    1.  **Acknowledge the User's Goal**: Start by briefly acknowledging what the user asked about.
    2.  **Summarize Key Findings**: Use bullet points to present the most important opportunities, risks, and recommendations from the analysis.
    3.  **Be Encouraging and Clear**: The tone should be supportive and the information easy to digest.
    4.  **Be Concise**: Do not copy the entire analysis. Extract the essence. The final response should be significantly shorter than the analysis.
    """
    
    human_prompt = f"""
    User's Original Query: {state['user_query']}
    
    Detailed Strategic Analysis:
    ---
    {state.get('final_analysis', 'Analysis not available.')}
    ---
    
    Based on this, generate the final response for the user.
    """
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"final_response": response.content}