"""
CompliSense Configuration — the single source of truth.

Every tunable in the system is defined here and imported by the code that uses
it. Do NOT hardcode model names, paths, or retrieval params elsewhere.

Provider/model selection is config-driven (see src/llm/provider.py) so that an
LLM-provider deprecation is a one-line change here, not a code hunt.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# --------------------------------------------------------------------------- #
# LLM provider & models (provider-abstraction layer reads these)
# --------------------------------------------------------------------------- #
# Supported providers:
#   "groq" | "google" | "openai" | "anthropic"
#   "openrouter" — OpenAI-compatible gateway to GLM-5.2, Gemma 4, and ~everything
#   "openai_compatible" — any OpenAI-compatible base_url (Z.ai, vLLM, Ollama, ...)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()

# Base URL for the OpenAI-compatible providers (override for Z.ai/local servers).
OPENAI_COMPAT_BASE_URL = os.getenv(
    "OPENAI_COMPAT_BASE_URL", "https://openrouter.ai/api/v1"
)

# Per-role model IDs. Roles: "reasoning" (answer/faithfulness) and "fast"
# (orchestrator/scope-guard). Defaults below are CURRENTLY-LIVE Groq models as
# of 2026-06 — NOTE: Groq has these scheduled for shutdown 2026-08-16, so treat
# the env vars as the real knob and verify against the provider's model list.
_MODEL_DEFAULTS = {
    "groq": {
        "reasoning": "llama-3.3-70b-versatile",
        "fast": "llama-3.1-8b-instant",
    },
    "google": {
        "reasoning": "gemini-2.5-pro",
        "fast": "gemini-2.5-flash",
    },
    "openai": {
        "reasoning": "gpt-4o",
        "fast": "gpt-4o-mini",
    },
    "anthropic": {
        "reasoning": "claude-opus-4-8",
        "fast": "claude-haiku-4-5-20251001",
    },
    # GLM-5.2 (1M ctx, MIT) for reasoning; Gemma 4 (MoE, cheap) for routing.
    "openrouter": {
        "reasoning": "z-ai/glm-5.2",
        "fast": "google/gemma-4-26b-a4b-it",
    },
    "openai_compatible": {
        "reasoning": "z-ai/glm-5.2",
        "fast": "google/gemma-4-26b-a4b-it",
    },
}

REASONING_MODEL = os.getenv(
    "REASONING_MODEL", _MODEL_DEFAULTS.get(LLM_PROVIDER, {}).get("reasoning", "")
)
FAST_MODEL = os.getenv(
    "FAST_MODEL", _MODEL_DEFAULTS.get(LLM_PROVIDER, {}).get("fast", "")
)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
# Bound output so we never blow the context window or run away on cost.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))


# --------------------------------------------------------------------------- #
# Retrieval / RAG
# --------------------------------------------------------------------------- #
# Full-quality retrieval for precision-critical legal text:
#   bge-large-en-v1.5 (1024d) dense embeddings + BM25 keyword recall (hybrid),
#   re-ranked by a cross-encoder. All CPU-runnable, just heavier than MiniLM.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# Cross-encoder reranker (set RERANK_ENABLED=false to skip on constrained hosts).
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-base")
# Hybrid dense + BM25 fusion (reciprocal-rank fusion weight on dense, 0..1).
HYBRID_ENABLED = os.getenv("HYBRID_ENABLED", "true").lower() == "true"
HYBRID_DENSE_WEIGHT = float(os.getenv("HYBRID_DENSE_WEIGHT", "0.5"))

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# NRPC — Normative-Recall-Preserving Compression of retrieved context.
# Keeps normative spans verbatim, drops boilerplate. Off by default; opt in
# once validated on real corpus via evals/nrpc_eval.py.
NRPC_ENABLED = os.getenv("NRPC_ENABLED", "false").lower() == "true"
# Fraction of non-normative token budget to retain (0 = drop all boilerplate).
NRPC_KEEP_RATIO = float(os.getenv("NRPC_KEEP_RATIO", "0.15"))

# Retrieve a wide candidate set (dense+BM25), rerank, then keep the top-K above
# threshold. CANDIDATE_K feeds the reranker; TOP_K is what reaches the LLM.
RETRIEVAL_CANDIDATE_K = int(os.getenv("RETRIEVAL_CANDIDATE_K", "20"))
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
# Cosine similarity floor (embeddings are normalized). Below this we treat the
# corpus as having NO grounded answer and refuse rather than hallucinate.
RETRIEVAL_SCORE_THRESHOLD = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.35"))

# Minimum chunks the ingestion must produce, else it fails loudly instead of
# silently shipping an empty/partial knowledge base.
MIN_EXPECTED_CHUNKS = int(os.getenv("MIN_EXPECTED_CHUNKS", "50"))


# --------------------------------------------------------------------------- #
# CAG (Cache-Augmented Generation) for the RBI agent
# --------------------------------------------------------------------------- #
# When the corpus fits the model window, preload it and skip retrieval. Only
# worthwhile if the provider caches the prefix (GLM-5.2 cached input ~$0.26/1M).
# OFF by default: it hard-crashes small-context providers (e.g. Groq) and, with
# a whole-corpus source list, weakens per-citation verification. Opt in ONLY on
# a large-context, prompt-caching provider (GLM-5.2 1M).
CAG_ENABLED = os.getenv("CAG_ENABLED", "false").lower() == "true"
# Safety ceiling (conservative chars/3 estimate); above this, fall back to retrieval.
CAG_MAX_CORPUS_TOKENS = int(os.getenv("CAG_MAX_CORPUS_TOKENS", "120000"))


# --------------------------------------------------------------------------- #
# Web search (PESTEL / Competitor / Trend agents — grounded on source URLs)
# --------------------------------------------------------------------------- #
TAVILY_SEARCH_DEPTH = os.getenv("TAVILY_SEARCH_DEPTH", "advanced")
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "5"))
# Hard cap on the Competitor agent's bounded-ReAct search loop.
COMPETITOR_MAX_SEARCHES = int(os.getenv("COMPETITOR_MAX_SEARCHES", "4"))

PESTEL_DOMAINS = [
    "rbi.org.in", "finance.gov.in", "tracxn.com",
    "yourstory.com", "economictimes.indiatimes.com",
]
COMPETITOR_DOMAINS = ["tracxn.com", "crunchbase.com", "yourstory.com", "inc42.com"]


# --------------------------------------------------------------------------- #
# Faithfulness gate (replaces the old LLM-judge validator)
# --------------------------------------------------------------------------- #
# How many times the failing agent may be re-run before we ship with a warning.
MAX_FAITHFULNESS_RETRIES = int(os.getenv("MAX_FAITHFULNESS_RETRIES", "1"))


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
RBI_DATA_PATH = os.getenv("RBI_DATA_PATH", "./data")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
DATA_SOURCES_FILE = os.getenv("DATA_SOURCES_FILE", "data_sources.yaml")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "rbi_compliance")


# --------------------------------------------------------------------------- #
# API keys (only the active provider's key is required)
# --------------------------------------------------------------------------- #
_PROVIDER_KEY_ENV = {
    "groq": "GROQ_API_KEY",
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai_compatible": "OPENAI_COMPAT_API_KEY",
}


# --------------------------------------------------------------------------- #
# Product guardrails
# --------------------------------------------------------------------------- #
DISCLAIMER = (
    "⚠️ **Informational only — not legal, financial, or regulatory advice.** "
    "CompliSense summarizes RBI documents that may be outdated, draft, or "
    "incomplete. Verify every point against the cited primary source and "
    "consult a qualified professional or the RBI directly before acting."
)


def validate_config() -> bool:
    """Validate that the active provider's key and a model id are present.

    Called at application/ingestion startup (see src/llm/provider.py and the
    UI) so misconfiguration fails fast with a clear message.
    """
    errors = []

    key_env = _PROVIDER_KEY_ENV.get(LLM_PROVIDER)
    if key_env is None:
        errors.append(
            f"LLM_PROVIDER='{LLM_PROVIDER}' is not supported. "
            f"Choose one of: {', '.join(_PROVIDER_KEY_ENV)}"
        )
    elif not os.getenv(key_env):
        errors.append(f"{key_env} is not set (required for LLM_PROVIDER={LLM_PROVIDER})")

    if not REASONING_MODEL:
        errors.append("REASONING_MODEL is not set and no default exists for the provider")
    if not FAST_MODEL:
        errors.append("FAST_MODEL is not set and no default exists for the provider")

    if errors:
        raise ValueError(
            "Invalid CompliSense configuration:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )
    return True


def provider_api_key() -> str:
    """Return the API key for the active provider (or raise)."""
    validate_config()
    return os.getenv(_PROVIDER_KEY_ENV[LLM_PROVIDER])
