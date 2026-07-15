"""
Provider-abstraction layer.

One interface, ``get_llm(role)``, returns a LangChain chat model for the
provider/model configured in src/config.py. Swapping providers (or surviving a
model deprecation) is a config change, never a code change.

Provider SDKs are imported lazily so only the *active* provider's package needs
to be installed.
"""

from functools import lru_cache
import os
import sys
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

from .. import config

Role = Literal["reasoning", "fast"]


def _looks_echoed(text: str) -> bool:
    """Detect the gemma-4-31b failure mode: the model restates the prompt
    ("Role: ... Task: ... Constraint ...") before/instead of answering. A quality
    failure is NOT an exception, so without this check a fallback chain would
    happily ship the garbage. Heuristic on the head of the output only."""
    head = (text or "")[:300].lower()
    return "role:" in head and ("constraint" in head or "task:" in head)


class _FallbackModel:
    def __init__(self, primary, fallback=None, *, role: Role):
        self._primary = primary
        self._fallback = fallback  # may itself be a _FallbackModel (chain)
        self._role = role

    def __getattr__(self, name):
        return getattr(self._primary, name)

    def _warn(self, reason: str) -> None:
        if self._fallback is None:
            return
        print(f"[llm fallback] role={self._role} {reason}; trying next provider in chain",
              file=sys.stderr)

    def invoke(self, messages, *args, **kwargs):
        try:
            result = self._primary.invoke(messages, *args, **kwargs)
        except Exception as primary_exc:  # noqa: BLE001
            if self._fallback is None:
                raise
            self._warn(f"primary failed: {type(primary_exc).__name__}: {primary_exc}")
            try:
                return self._fallback.invoke(messages, *args, **kwargs)
            except Exception as fallback_exc:  # noqa: BLE001
                raise fallback_exc from primary_exc

        # QUALITY gate: prompt-echo output (gemma-4-31b defect) falls through the
        # chain; if every fallback also fails, ship the primary output rather than crash.
        if self._fallback is not None and _looks_echoed(getattr(result, "content", "")):
            self._warn("primary output looks like prompt-echo (quality gate)")
            try:
                return self._fallback.invoke(messages, *args, **kwargs)
            except Exception:  # noqa: BLE001
                return result
        return result

    def with_structured_output(self, schema, *args, **kwargs):
        primary = getattr(self._primary, "with_structured_output", None)
        fallback = getattr(self._fallback, "with_structured_output", None)

        if callable(primary) and callable(fallback):
            return _FallbackModel(
                primary(schema, *args, **kwargs),
                fallback(schema, *args, **kwargs),
                role=self._role,
            )

        if callable(primary):
            return primary(schema, *args, **kwargs)

        if callable(fallback):
            return fallback(schema, *args, **kwargs)

        raise AttributeError("No structured-output implementation available")


def _model_for(role: Role) -> str:
    model = config.REASONING_MODEL if role == "reasoning" else config.FAST_MODEL
    if not model:
        raise ValueError(f"No model configured for role '{role}'. Check config.")
    return model


def _fallback_model_for(role: Role) -> str:
    model = (
        config.OPENROUTER_REASONING_MODEL if role == "reasoning" else config.OPENROUTER_FAST_MODEL
    )
    if not model:
        raise ValueError(f"No fallback model configured for role '{role}'. Check config.")
    return model


def _openrouter_llm(role: Role):
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return ChatOpenAI(
        api_key=api_key,
        base_url=config.OPENAI_COMPAT_BASE_URL,
        model=_fallback_model_for(role),
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )


def _google_llm(role: Role):
    """Gemini via raw REST — used as the FALLBACK when OpenRouter is the primary
    (e.g. it runs out of credits). Returns None if no Google key is set."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    from .gemini_rest import GeminiRESTChat

    model = config.GOOGLE_REASONING_MODEL if role == "reasoning" else config.GOOGLE_FAST_MODEL
    return GeminiRESTChat(
        model=model, api_key=api_key,
        temperature=config.LLM_TEMPERATURE, max_tokens=config.LLM_MAX_TOKENS,
        thinking_level=config.GEMINI_THINKING.get(role),
    )


def _groq_llm(role: Role):
    """Groq via its OpenAI-compatible endpoint (no langchain_groq dependency).
    Free-tier friendly, ~500 tok/s; qwen3.6-27b has native JSON mode + tool use."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    from langchain_openai import ChatOpenAI

    model = config.GROQ_REASONING_MODEL if role == "reasoning" else config.GROQ_FAST_MODEL
    return ChatOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        model=model,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
    )


_FB_BUILDERS = {
    "google": _google_llm,
    "groq": _groq_llm,
    "openrouter": _openrouter_llm,
    "openai_compatible": _openrouter_llm,
}


def _fallback_llm(role: Role):
    """Build the configured fallback CHAIN (or None).

    LLM_FALLBACK_PROVIDER accepts a comma-separated list, e.g. "google,groq" =
    try google's fallback model first, then groq. Same-provider fallback is fine
    when the MODEL differs (e.g. gemma primary -> gemini-3.5-flash fallback, both
    google): the fallback google model comes from GOOGLE_*_MODEL, not *_MODEL.
    Chain is realised by nesting _FallbackModel instances.
    """
    chain = []
    for name in (p.strip() for p in config.LLM_FALLBACK_PROVIDER.split(",")):
        builder = _FB_BUILDERS.get(name)
        llm = builder(role) if builder else None
        if llm is not None:
            chain.append(llm)
    fallback = None
    for llm in reversed(chain):
        fallback = llm if fallback is None else _FallbackModel(llm, fallback, role=role)
    return fallback


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
        # OpenAI-compatible endpoint — avoids the langchain_groq dependency.
        from langchain_openai import ChatOpenAI

        primary = ChatOpenAI(
            api_key=api_key, base_url="https://api.groq.com/openai/v1", **common
        )
        return _FallbackModel(primary, _fallback_llm(role), role=role)

    if provider == "google":
        # Raw REST (see gemini_rest): avoids langchain-google-genai protobuf clash.
        from .gemini_rest import GeminiRESTChat

        primary = GeminiRESTChat(
            model=model, api_key=api_key,
            temperature=config.LLM_TEMPERATURE, max_tokens=config.LLM_MAX_TOKENS,
            thinking_level=config.GEMINI_THINKING.get(role),
        )
        return _FallbackModel(primary, _fallback_llm(role), role=role)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(api_key=api_key, **common)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(api_key=api_key, **common)

    if provider in ("openrouter", "openai_compatible"):
        # Single OpenAI-compatible path: GLM-5.2, Gemma 4, Z.ai, vLLM, Ollama, ...
        from langchain_openai import ChatOpenAI

        primary = ChatOpenAI(
            api_key=api_key,
            base_url=config.OPENAI_COMPAT_BASE_URL,
            **common,
        )
        # If OpenRouter can't answer (e.g. out of credits / rate-limited), fall
        # back to the configured provider (typically google) so the run still works.
        fallback = _fallback_llm(role) if config.LLM_FALLBACK_PROVIDER != provider else None
        return _FallbackModel(primary, fallback, role=role)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}")
