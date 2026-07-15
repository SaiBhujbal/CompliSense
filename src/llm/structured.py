"""Robust structured-output helper.

Not every model behind the OpenAI-compatible path (GLM, Gemma, Llama via
OpenRouter) reliably supports `with_structured_output`'s function-calling mode.
This tries that first, then falls back to JSON-mode prompting with tolerant
parsing, and only then returns the caller-supplied fallback. Critically, the
CALLER chooses the fallback — so safety-critical nodes (faithfulness) can fail
CLOSED rather than open.
"""

import json
import re
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def safe_invoke(llm, messages: list, *, fallback: str) -> str:
    """Plain-text invoke that NEVER raises. A single agent hitting a rate-limit (or
    a dead provider fallback) must not crash the whole multi-agent run — it returns
    a degraded report and the graph continues to synthesis."""
    try:
        r = llm.invoke(messages)
        text = getattr(r, "content", None)
        return text if (text and text.strip()) else fallback
    except Exception:  # noqa: BLE001
        return fallback


def invoke_structured(llm, schema: type[T], messages: list, *, fallback: T) -> T:
    # 1. Native structured output (best when supported).
    try:
        return llm.with_structured_output(schema).invoke(messages)
    except Exception:
        pass

    # 2. JSON-mode prompt + tolerant parse.
    try:
        from langchain_core.messages import SystemMessage

        keys = list(schema.model_fields.keys())
        hint = SystemMessage(
            content=f"Respond with ONLY a valid JSON object with keys {keys}. "
            "No prose, no markdown fences."
        )
        raw = llm.invoke(list(messages) + [hint])
        text = getattr(raw, "content", str(raw))
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return schema(**json.loads(match.group(0)))
    except Exception:
        pass

    # 3. Caller-defined fallback (lets safety nodes fail closed).
    return fallback
