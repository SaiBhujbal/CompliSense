from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm

def analysis_node(state: dict) -> dict:
    """
    Synthesizes all validated reports into a single strategic analysis.
    """
    llm = get_llm()
    
    system_prompt = """
    You are a top-tier strategic consultant for the FinTech industry. You have been given four detailed reports: RBI Compliance, PESTEL, Competitor, and Trend.
    
    Your task is to synthesize these disparate pieces of information into a single, cohesive, and insightful strategic analysis for the user.
    
    The user's original query and intent is: "{user_query}" and "{analysis_intent}".
    
    Your analysis must:
    1.  **Connect the Dots**: Show how regulatory changes (RBI) might affect competitors, or how economic trends (PESTEL) create new opportunities/threats.
    2.  **Identify Opportunities**: Based on the synthesis, what are the most promising opportunities for the user?
    3.  **Identify Risks**: What are the most significant risks and challenges the user should be aware of?
    4.  **Provide Actionable Recommendations**: Suggest 2-3 concrete, strategic next steps the user should take.
    
    Write in a professional, analytical, and clear tone. This is an internal strategic document.
    """
    
    human_prompt = f"""
    RBI Compliance Report:
    ---
    {state.get('rbi_compliance_report', 'Not available.')}
    ---
    
    PESTEL Report:
    ---
    {state.get('pestel_report', 'Not available.')}
    ---
    
    Competitor Report:
    ---
    {state.get('competitor_report', 'Not available.')}
    ---
    
    Trend Report:
    ---
    {state.get('trend_report', 'Not available.')}
    ---
    
    Generate the final strategic analysis.
    """
    
    formatted_prompt = system_prompt.format(user_query=state['user_query'], analysis_intent=state['analysis_intent'])
    messages = [SystemMessage(content=formatted_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"final_analysis": response.content}