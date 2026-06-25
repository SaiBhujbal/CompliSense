"""
Provider-abstraction layer.

One interface, ``get_llm(role)``, returns a LangChain chat model for the
provider/model configured in src/config.py. Swapping providers (or surviving a
model deprecation) is a config change, never a code change.

Provider SDKs are imported lazily so only the *active* provider's package needs
to be installed.
"""

from functools import lru_cache
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from .. import config

Role = Literal["reasoning", "fast"]


def _model_for(role: Role) -> str:
    model = config.REASONING_MODEL if role == "reasoning" else config.FAST_MODEL
    if not model:
        raise ValueError(f"No model configured for role '{role}'. Check config.")
    return model


@lru_cache(maxsize=8)
def get_llm(role: Role = "reasoning") -> BaseChatModel:
    """Return a chat model for the given role, cached per (provider, role).

    ``role='reasoning'`` -> answer/faithfulness; ``role='fast'`` -> orchestrator.
    """
    config.validate_config()
    provider = config.LLM_PROVIDER
    model = _model_for(role)
    api_key = config.provider_api_key()
    common = dict(
        model=model,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(api_key=api_key, **common)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # langchain-google-genai uses max_output_tokens
        return ChatGoogleGenerativeAI(
            google_api_key=api_key,
            max_output_tokens=config.LLM_MAX_TOKENS,
            model=model,
            temperature=config.LLM_TEMPERATURE,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(api_key=api_key, **common)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(api_key=api_key, **common)

    if provider in ("openrouter", "openai_compatible"):
        # Single OpenAI-compatible path: GLM-5.2, Gemma 4, Z.ai, vLLM, Ollama, ...
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=api_key,
            base_url=config.OPENAI_COMPAT_BASE_URL,
            **common,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}")
