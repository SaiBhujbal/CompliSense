import os
from langchain_groq import ChatGroq
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_llm(model_name: str = "llama3-70b-8192"):
    """Initializes and returns a Groq LLM instance."""
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables.")
    return ChatGroq(model=model_name, api_key=groq_api_key, temperature=0.1)

def setup_vector_store() -> Chroma:
    """
    Loads an existing Chroma vector store. Expects the store to be created
    by the `ingest_data.py` script.
    """
    db_path = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Vector store not found at {db_path}. "
            "Please run 'python ingest_data.py' from the root directory to create it."
        )
    
    print(f"Loading existing vector store from {db_path}")
    # Use HuggingFace embeddings (free, no API key required)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    vector_store = Chroma(persist_directory=db_path, embedding_function=embeddings)
    return vector_store