"""Configurable LLM provider abstraction.

Supports, in order (llm_provider = "auto"):
    1. Ollama   — local models via OLLAMA_BASE_URL / OLLAMA_MODEL
    2. Hugging Face Inference API — HF_TOKEN / HF_MODEL_ID
    3. Rule-based fallback — deterministic extractors (no model call)

No paid API is required. When no provider is reachable, agents receive
`llm_mode="rule-based-fallback"` and compute answers from real input data
instead of returning hardcoded text.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger("shopmate.llm")
T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResult:
    """Outcome of a structured completion attempt."""

    data: Optional[BaseModel]
    mode: str  # "ollama" | "huggingface" | "rule-based-fallback"
    raw: str = ""
    error: Optional[str] = None


class LLMProviderError(Exception):
    pass


class LLMClient(ABC):
    name: str = "base"

    @abstractmethod
    async def complete_json(self, system: str, user: str, schema: Type[T]) -> LLMResult:
        """Ask the model for JSON matching `schema`; raise on hard failure."""

    async def health(self) -> bool:
        try:
            res = await self.complete_json(
                "Reply with JSON.", 'Return {"ok": true}', type(HealthSchema)  # type: ignore[arg-type]
            )
            return res.data is not None
        except Exception:
            return False


class HealthSchema(BaseModel):
    ok: bool = True


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model response (handles ```json)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start == -1:
        raise LLMProviderError("no JSON object in response")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise LLMProviderError("unbalanced JSON in response")


def _validate(payload: dict[str, Any], schema: Type[T]) -> T:
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise LLMProviderError(f"schema validation failed: {exc.errors()[0]['msg']}") from exc


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model

    async def complete_json(self, system: str, user: str, schema: Type[T]) -> LLMResult:
        prompt = (
            f"{system}\n\nRespond with ONLY a valid JSON object that matches "
            f"this JSON schema:\n{json.dumps(schema.model_json_schema())}\n\n"
            f"User input:\n{user}"
        )
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.0},
                    },
                )
                resp.raise_for_status()
                text = resp.json().get("response", "")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LLMProviderError(f"ollama unavailable: {exc}") from exc

        data = _extract_json(text)
        return LLMResult(data=_validate(data, schema), mode=self.name, raw=text)


class HuggingFaceClient(LLMClient):
    name = "huggingface"

    def __init__(self) -> None:
        self.model = settings.hf_model_id
        self.api_url = f"{settings.hf_api_url.rstrip('/')}/{self.model}"

    async def complete_json(self, system: str, user: str, schema: Type[T]) -> LLMResult:
        headers = {"Authorization": f"Bearer {settings.hf_token}"}
        prompt = (
            f"{system}\n\nReturn ONLY JSON matching:\n"
            f"{json.dumps(schema.model_json_schema())}\n\nUser:\n{user}"
        )
        payload = {
            "inputs": prompt,
            "parameters": {"temperature": 0.0, "return_full_text": False, "max_new_tokens": 600},
        }
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                resp = await client.post(self.api_url, headers=headers, json=payload)
                if resp.status_code == 503:  # model loading
                    raise LLMProviderError("hf model loading, retry later")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMProviderError(f"huggingface unavailable: {exc}") from exc

        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "") or data[0].get("summary_text", "")
        elif isinstance(data, dict):
            text = data.get("generated_text", "") or json.dumps(data)
        else:
            raise LLMProviderError("unexpected hf response shape")
        return LLMResult(data=_validate(_extract_json(text), schema), mode=self.name, raw=text)


class NullClient(LLMClient):
    """Explicitly signals 'no model configured' to the agents."""

    name = "none"

    async def complete_json(self, system: str, user: str, schema: Type[T]) -> LLMResult:
        return LLMResult(data=None, mode="rule-based-fallback",
                         error="no_llm_provider_configured")


_cached: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """Return the configured LLM client (cheap to call; cached)."""
    global _cached
    if _cached is not None:
        return _cached

    choice = (settings.llm_provider or "auto").lower()
    client: LLMClient = NullClient()

    if choice in ("ollama", "auto") and settings.ollama_base_url:
        client = OllamaClient()
    elif choice == "huggingface" and settings.hf_token:
        client = HuggingFaceClient()
    elif choice == "auto" and settings.hf_token:
        client = HuggingFaceClient()

    _cached = client
    return client


def reset_llm_cache() -> None:
    """Test helper — re-resolve the provider after settings change."""
    global _cached
    _cached = None


async def structured_completion(
    system: str, user: str, schema: Type[T], fallback: Optional[T] = None
) -> LLMResult:
    """Try the configured model; degrade to `fallback` on any failure.

    Agents call this instead of the client directly so that a dead Ollama/HF
    endpoint never breaks the graph.
    """
    client = get_llm()
    if isinstance(client, NullClient):
        return LLMResult(data=fallback, mode="rule-based-fallback",
                         error="no_llm_provider_configured")
    try:
        return await client.complete_json(system, user, schema)
    except Exception as exc:
        logger.warning("llm_failed provider=%s error=%s", client.name, exc)
        return LLMResult(data=fallback, mode="rule-based-fallback", error=str(exc))
