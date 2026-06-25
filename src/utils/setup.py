"""Back-compat shim.

Prefer importing directly:
  - LLM:        from src.llm import get_llm        # get_llm("reasoning"|"fast")
  - vector store: from src.rag.retriever import get_vector_store
This module remains only so older imports don't break.
"""

from ..llm import get_llm
from ..rag.retriever import get_vector_store as setup_vector_store

__all__ = ["get_llm", "setup_vector_store"]
