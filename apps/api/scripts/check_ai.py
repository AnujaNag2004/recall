"""Checks your AI setup: lists usable models and tries each configured provider.

Run with `make check-ai`. Prints no keys.
"""

import asyncio

import httpx

from app.core.config import get_settings
from app.providers.base import ProviderError
from app.providers.registry import get_providers


async def list_models() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=20) as client:
        if settings.gemini_api_key:
            r = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
            if r.status_code == 200:
                print("\nGemini models:")
                for model in r.json().get("models", []):
                    methods = model.get("supportedGenerationMethods", [])
                    use = [m for m in ("generateContent", "embedContent") if m in methods]
                    if use:
                        print(f"  {model['name'].removeprefix('models/')}  ({', '.join(use)})")
            else:
                print(f"\nGemini model list failed: HTTP {r.status_code}")
        if settings.groq_api_key:
            r = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
            if r.status_code == 200:
                print("\nGroq models:")
                for model in sorted(m["id"] for m in r.json().get("data", [])):
                    print(f"  {model}")
            else:
                print(f"\nGroq model list failed: HTTP {r.status_code}")


async def attempt(name: str, call) -> None:  # type: ignore[no-untyped-def]
    try:
        result = await call
        print(f"  OK    {name}: {str(result)[:60]!r}")
    except ProviderError as error:
        print(f"  FAIL  {name}: {error}")


async def main() -> None:
    await list_models()
    providers = get_providers()
    print("\nTrying each provider:")
    await attempt("LLM", providers.llm.complete("Reply with the word ready."))
    await attempt("Embeddings", providers.embeddings.embed(["hello"]))
    await attempt("Search", providers.search.search("official python website", max_results=1))
    print("\nTranscription is checked the first time you upload audio.")


asyncio.run(main())
