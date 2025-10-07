"""
CompliSense Utilities Package

This package contains utility functions for LLM initialization,
vector store setup, and other shared functionality.
"""

from .setup import get_llm, setup_vector_store

__all__ = ['get_llm', 'setup_vector_store']
