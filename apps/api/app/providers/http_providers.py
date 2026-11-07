"""Gemini, Groq and Tavily, called over their REST APIs."""

import asyncio
import base64
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import (
    ModelTier,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRateLimitedError,
    SearchResult,
    TranscriptSegment,
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
GROQ_URL = "https://api.groq.com/openai/v1"
TAVILY_URL = "https://api.tavily.com/search"
TIMEOUT = httpx.Timeout(120, connect=10)


def _raise_for_status(provider: str, response: httpx.Response) -> None:
    # Bodies are deliberately left out: they can echo the submitted content.
    if response.status_code == 429:
        raise ProviderRateLimitedError(f"{provider} rate limit reached")
    if response.status_code >= 400:
        raise ProviderError(f"{provider} returned HTTP {response.status_code}")


def _require(value: str | None, setting: str) -> str:
    if not value:
        raise ProviderNotConfiguredError(f"{setting} is not set")
    return value


class GeminiProvider:
    name = "gemini"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=TIMEOUT)

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": _require(self._settings.gemini_api_key, "GEMINI_API_KEY")}

    async def _generate(self, model: str, body: dict[str, Any]) -> str:
        try:
            response = await self._client.post(
                f"{GEMINI_URL}/models/{model}:generateContent", headers=self._headers(), json=body
            )
        except httpx.HTTPError as error:
            raise ProviderError("Could not reach Gemini") from error
        _raise_for_status("Gemini", response)
        candidates = response.json().get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(part.get("text", "") for part in parts)
        if not text:
            raise ProviderError("Gemini returned no text")
        return text

    def _model(self, tier: ModelTier) -> str:
        if tier == ModelTier.STRONG:
            return _require(self._settings.gemini_strong_model, "GEMINI_STRONG_MODEL")
        return _require(self._settings.gemini_fast_model, "GEMINI_FAST_MODEL")

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_mode: bool = False,
    ) -> str:
        body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        return await self._generate(self._model(tier), body)

    async def describe_media(self, data: bytes, mime_type: str, prompt: str) -> str:
        inline = {"mimeType": mime_type, "data": base64.b64encode(data).decode()}
        body = {"contents": [{"role": "user", "parts": [{"inlineData": inline}, {"text": prompt}]}]}
        return await self._generate(self._model(ModelTier.FAST), body)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = _require(self._settings.gemini_embedding_model, "GEMINI_EMBEDDING_MODEL")
        requests = [
            {
                "model": f"models/{model}",
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": self._settings.embedding_dim,
            }
            for text in texts
        ]
        try:
            response = await self._client.post(
                f"{GEMINI_URL}/models/{model}:batchEmbedContents",
                headers=self._headers(),
                json={"requests": requests},
            )
        except httpx.HTTPError as error:
            raise ProviderError("Could not reach Gemini") from error
        _raise_for_status("Gemini", response)
        embeddings = [item["values"] for item in response.json().get("embeddings", [])]
        if len(embeddings) != len(texts):
            raise ProviderError("Gemini returned the wrong number of embeddings")
        if any(len(vector) != self._settings.embedding_dim for vector in embeddings):
            raise ProviderError("Embedding size doesn't match EMBEDDING_DIM")
        return embeddings


class GroqProvider:
    name = "groq"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=TIMEOUT)

    def _headers(self) -> dict[str, str]:
        key = _require(self._settings.groq_api_key, "GROQ_API_KEY")
        return {"Authorization": f"Bearer {key}"}

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_mode: bool = False,
    ) -> str:
        model = (
            _require(self._settings.groq_strong_model, "GROQ_STRONG_MODEL")
            if tier == ModelTier.STRONG
            else _require(self._settings.groq_fast_model, "GROQ_FAST_MODEL")
        )
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"model": model, "messages": messages}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            response = await self._client.post(
                f"{GROQ_URL}/chat/completions", headers=self._headers(), json=body
            )
        except httpx.HTTPError as error:
            raise ProviderError("Could not reach Groq") from error
        _raise_for_status("Groq", response)
        content = response.json()["choices"][0]["message"].get("content")
        if not content:
            raise ProviderError("Groq returned no text")
        return str(content)

    async def describe_media(self, data: bytes, mime_type: str, prompt: str) -> str:
        raise ProviderNotConfiguredError("Groq has no media understanding here")

    async def transcribe(
        self, data: bytes, filename: str, mime_type: str
    ) -> list[TranscriptSegment]:
        model = _require(self._settings.groq_whisper_model, "GROQ_WHISPER_MODEL")
        try:
            response = await self._client.post(
                f"{GROQ_URL}/audio/transcriptions",
                headers=self._headers(),
                data={"model": model, "response_format": "verbose_json"},
                files={"file": (filename, data, mime_type)},
            )
        except httpx.HTTPError as error:
            raise ProviderError("Could not reach Groq") from error
        _raise_for_status("Groq", response)
        return [
            TranscriptSegment(float(s["start"]), float(s["end"]), str(s["text"]).strip())
            for s in response.json().get("segments", [])
        ]


class TavilyProvider:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=TIMEOUT)

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        key = _require(self._settings.tavily_api_key, "TAVILY_API_KEY")
        try:
            response = await self._client.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"query": query, "max_results": max_results},
            )
        except httpx.HTTPError as error:
            raise ProviderError("Could not reach Tavily") from error
        _raise_for_status("Tavily", response)
        return [
            SearchResult(
                title=str(item.get("title", "")),
                url=str(item["url"]),
                snippet=str(item.get("content", "")),
                score=float(item.get("score", 0)),
            )
            for item in response.json().get("results", [])
        ]


class FallbackLLM:
    """Tries each provider in turn, moving on when one is throttled, failing or unset."""

    name = "fallback"

    def __init__(self, providers: list[Any], backoff_seconds: float = 1.0) -> None:
        self._providers = providers
        self._backoff = backoff_seconds

    async def _first_success(self, call: Any) -> str:
        last_error: ProviderError | None = None
        for index, provider in enumerate(self._providers):
            if index:
                await asyncio.sleep(self._backoff)
            try:
                return str(await call(provider))
            except ProviderError as error:
                last_error = error
        raise last_error or ProviderNotConfiguredError("No LLM provider configured")

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_mode: bool = False,
    ) -> str:
        return await self._first_success(
            lambda p: p.complete(prompt, system=system, tier=tier, json_mode=json_mode)
        )

    async def describe_media(self, data: bytes, mime_type: str, prompt: str) -> str:
        return await self._first_success(lambda p: p.describe_media(data, mime_type, prompt))
