import os
from tavily import TavilyClient
from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def competitor_node(state: dict) -> dict:
    """
    Identifies and analyzes competitors based on the user's business idea.
    """
    llm = get_llm()
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return {"competitor_report": "TAVILY_API_KEY not configured. Cannot perform competitor analysis."}
    
    tavily = TavilyClient(api_key=tavily_api_key)
    
    # Extract business category from the user's intent
    search_query = f"competitors for {state['analysis_intent']} in India funding news"
    
    try:
        search_result = tavily.search(query=search_query, search_depth="advanced", include_domains=["tracxn.com", "crunchbase.com", "yourstory.com", "inc42.com"])
        context = "\n".join([obj["content"] for obj in search_result["results"]])
    except Exception as e:
        return {"competitor_report": f"Failed to fetch data using Tavily: {e}"}

    system_prompt = """
    You are a market intelligence analyst. Your task is to analyze the competitive landscape based on the provided search results.
    
    1.  **Identify Key Competitors**: List 3-5 main companies in the specified business category.
    2.  **Analyze Each Competitor**: For each competitor, provide:
        -   Business Model Summary
        -   Key Products/Services
        -   Recent Funding (if available)
        -   Perceived Strengths and Weaknesses
    3.  **Synthesize a Competitive Overview**: Briefly describe the overall market dynamics (e.g., Is it crowded? Dominated by a few players? Is it a growing market?).
    
    If the search results do not contain enough information, state that clearly. Do not invent competitor details.
    """
    
    human_prompt = f"User's business idea: {state['analysis_intent']}\n\nSearch Results:\n---\n{context}\n---\n\nGenerate the competitor analysis report."
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"competitor_report": response.content}