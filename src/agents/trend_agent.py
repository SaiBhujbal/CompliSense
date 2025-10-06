import os
from tavily import TavilyClient
from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def trend_node(state: dict) -> dict:
    """
    Predicts trends in the FinTech sector based on the user's query.
    """
    llm = get_llm()
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return {"trend_report": "TAVILY_API_KEY not configured. Cannot perform trend prediction."}
    
    tavily = TavilyClient(api_key=tavily_api_key)
    
    search_query = f"latest trends and future predictions for FinTech in India {state['analysis_intent']}"
    
    try:
        search_result = tavily.search(query=search_query, search_depth="advanced", include_raw_content=True, max_results=5)
        context = "\n".join([obj.get("raw_content", obj["content"]) for obj in search_result["results"]])
    except Exception as e:
        return {"trend_report": f"Failed to fetch data using Tavily: {e}"}

    system_prompt = """
    You are a futurist and data scientist specializing in financial technology.
    Based on the provided search results, identify and predict key trends in the Indian FinTech sector relevant to the user's interest.
    
    Your report should:
    1.  **Identify Current Trends**: What are the most significant developments happening right now?
    2.  **Predict Future Trends**: Based on current data, what is likely to happen in the next 1-2 years?
    3.  **Provide Statistical Insights**: If any data points (e.g., market growth rates, user adoption) are mentioned, highlight them.
    4.  **Connect to User's Goal**: Relate these trends back to the user's query. For example, "This trend towards [X] could be a significant opportunity for your P2P lending platform because..."
    
    Base your predictions strictly on the provided data. Avoid making unsubstantiated claims.
    """
    
    human_prompt = f"User's area of interest: {state['analysis_intent']}\n\nSearch Results:\n---\n{context}\n---\n\nGenerate the trend prediction report."
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"trend_report": response.content}