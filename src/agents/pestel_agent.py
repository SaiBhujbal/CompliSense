import os
from tavily import TavilyClient
from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def pestel_node(state: dict) -> dict:
    """
    Performs a PESTEL analysis for the Indian FinTech sector based on the user's query.
    """
    llm = get_llm()
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return {"pestel_report": "TAVILY_API_KEY not configured. Cannot perform PESTEL analysis."}
    
    tavily = TavilyClient(api_key=tavily_api_key)
    
    # Create a comprehensive search query
    search_query = f"latest PESTEL analysis for FinTech sector in India {state['analysis_intent']}"
    
    try:
        search_result = tavily.search(query=search_query, search_depth="advanced", include_domains=["rbi.org.in", "finance.gov.in", "tracxn.com", "yourstory.com", "economictimes.indiatimes.com"])
        context = "\n".join([obj["content"] for obj in search_result["results"]])
    except Exception as e:
        return {"pestel_report": f"Failed to fetch data using Tavily: {e}"}

    system_prompt = """
    You are a strategic analyst specializing in macro-environmental analysis.
    Based on the provided search results, conduct a detailed PESTEL analysis for the Indian FinTech sector.
    
    Structure your response clearly with the following headings:
    - **P**olitical: Government policies, regulatory changes, political stability.
    - **E**conomic: Economic growth, inflation, interest rates, investment climate.
    - **S**ocial: Cultural trends, consumer behavior, demographics.
    - **T**echnological: New technologies, innovation, digital adoption rates.
    - **E**nvironmental: Climate change policies, sustainability regulations.
    - **L**egal: Laws, regulations, compliance requirements beyond RBI.
    
    Synthesize the information into a coherent report. If information for a category is missing, state "Insufficient data found."
    """
    
    human_prompt = f"User's core interest: {state['analysis_intent']}\n\nSearch Results:\n---\n{context}\n---\n\nGenerate the PESTEL report."
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"pestel_report": response.content}