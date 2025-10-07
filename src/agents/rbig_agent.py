from langchain_core.messages import HumanMessage, SystemMessage
from . import get_llm
from ..utils.setup import setup_vector_store

def rbig_node(state: dict) -> dict:
    """
    Uses RAG to answer questions about RBI compliance.
    """
    llm = get_llm()
    vector_store = setup_vector_store()
    
    system_prompt = """
    You are a highly experienced expert on RBI (Reserve Bank of India) regulations, especially concerning FinTech, NBFCs, and digital lending.
    Your task is to answer the user's query based *only* on the provided context from official RBI documents.
    
    - If the context provides a clear answer, synthesize it into a comprehensive, precise, and easy-to-understand response.
    - If the context is partially relevant, use it to answer what you can and clearly state what information is missing.
    - If the context is not relevant to the query, state that you could not find specific information in the provided documents.
    - Do not invent information or make assumptions beyond the text.
    - Cite the source document if possible (e.g., "As per the Master Direction on Digital Lending...").
    """
    
    # Retrieve relevant documents
    retriever = vector_store.as_retriever(search_kwargs={"k": 5})
    relevant_docs = retriever.invoke(state['user_query'])
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    human_prompt = f"""
    User's Query: {state['user_query']}
    
    Context from RBI Documents:
    ---
    {context}
    ---
    
    Based on the context, please answer the user's query.
    """
    
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
    response = llm.invoke(messages)
    
    return {"rbi_compliance_report": response.content}