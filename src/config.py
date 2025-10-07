"""
CompliSense Configuration

Central configuration file for all system constants and settings.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# LLM Configuration
DEFAULT_LLM_MODEL = "llama3-70b-8192"
FAST_LLM_MODEL = "llama3-8b-8192"  # For orchestrator and validator
LLM_TEMPERATURE = 0.1

# Vector Store Configuration
DEFAULT_CHROMA_DB_PATH = "./chroma_db"
RETRIEVAL_TOP_K = 5
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Workflow Configuration
MAX_VALIDATION_RETRIES = 2
WORKFLOW_TIMEOUT = 300  # seconds

# Tavily Search Configuration
TAVILY_SEARCH_DEPTH = "advanced"
TAVILY_MAX_RESULTS = 5

# Domain Filters for Tavily
PESTEL_DOMAINS = [
    "rbi.org.in",
    "finance.gov.in", 
    "tracxn.com",
    "yourstory.com",
    "economictimes.indiatimes.com"
]

COMPETITOR_DOMAINS = [
    "tracxn.com",
    "crunchbase.com",
    "yourstory.com",
    "inc42.com"
]

# API Keys (loaded from environment)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# Note: OpenAI API key is no longer required - we use HuggingFace embeddings instead

# Data Paths
RBI_DATA_PATH = os.getenv("RBI_DATA_PATH", "./data")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", DEFAULT_CHROMA_DB_PATH)

# Validate required API keys
def validate_config():
    """Validate that all required configuration is present."""
    errors = []
    
    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY is not set")
    if not TAVILY_API_KEY:
        errors.append("TAVILY_API_KEY is not set")
    # OpenAI API key is no longer required - we use free HuggingFace embeddings
    
    if errors:
        raise ValueError(
            "Missing required configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    
    return True
