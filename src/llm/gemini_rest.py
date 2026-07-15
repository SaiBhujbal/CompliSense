"""
Dependency-free Google Generative Language (Gemini/Gemma) chat model via raw REST.

We deliberately bypass langchain-google-genai: its pinned protobuf schema clashes
with the installed google-ai-generativelanguage ("Unknown field for Part: thought"),
and chasing those pins triggers numpy source rebuilds. The raw generateContent
endpoint is stable and has no such conflicts. Duck-typed to the bits the agents
use: .invoke(messages) -> AIMessage(.content). Structured-output calls degrade
gracefully via src/llm/structured.invoke_structured (no with_structured_output here).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from langchain_core.messages import AIMessage

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={key}"


class GeminiRESTChat:
    def __init__(self, model: str, api_key: str, temperature: float = 0.1,
                 max_tokens: int = 1024, thinking_level: str | None = None):
        self.model = model if model.startswith("models/") else f"models/{model}"
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        # thinkingLevel is a Gemini-3 feature; only send it for gemini-3.x models.
        self.thinking_level = thinking_level if "gemini-3" in self.model else None

    def _to_prompt(self, messages) -> str:
        if isinstance(messages, str):
            return messages
        parts = []
        for m in messages:
            c = getattr(m, "content", None)
            parts.append(c if isinstance(c, str) else str(m if c is None else c))
        return "\n\n".join(parts)

    def _call(self, text: str, retries: int = 7) -> str:
        url = _ENDPOINT.format(model=self.model, key=self.api_key)
        out_tokens = self.max_tokens
        if "gemini-3" in self.model:
            # Gemini-3 THINKING tokens are billed against maxOutputTokens. With a
            # tight budget the model spends it all reasoning and the visible answer
            # gets truncated to a sentence. Give deep reports real room.
            out_tokens = max(out_tokens, 8192)
        gen_cfg = {"maxOutputTokens": out_tokens}
        if "gemini-3" not in self.model:  # Gemini 3.x: temperature/top_p/top_k deprecated
            gen_cfg["temperature"] = self.temperature
        if self.thinking_level:
            gen_cfg["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        body = json.dumps({"contents": [{"parts": [{"text": text}]}], "generationConfig": gen_cfg}).encode()
        last = ""
        # Cap attempts so rate-limit burnout hands off to LLM_FALLBACK_PROVIDER
        # instead of blocking Ask AI for minutes (7×~40s used to starve the chain).
        rate_limit_attempts = 0
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.load(r)
                cands = d.get("candidates", [])
                if not cands:
                    return ""
                parts = cands[0].get("content", {}).get("parts", [])
                return "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code == 429:
                    rate_limit_attempts += 1
                    # Fail fast to provider fallback after 2 brief backoffs (~6s total).
                    if rate_limit_attempts >= 3:
                        break
                    time.sleep(min(2 * rate_limit_attempts, 4))
                    continue
                if e.code in (500, 503):
                    time.sleep(min(3 * (attempt + 1), 20))
                    continue
                break
            except Exception as ex:  # noqa: BLE001
                last = f"{type(ex).__name__}: {ex}"
                time.sleep(2)
        raise RuntimeError(f"Gemini REST call failed after {retries} tries: {last}")

    def invoke(self, messages, *args, **kwargs) -> AIMessage:
        return AIMessage(content=self._call(self._to_prompt(messages)))
