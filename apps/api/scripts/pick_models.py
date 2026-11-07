"""Fills the model ID settings in .env, from the models your own keys can use.

Run with `make pick-models`. Model names change often, so asking the providers beats any
list written here. It never overwrites a value you've set, and it never prints keys.
"""

import asyncio
import re
import sys
from pathlib import Path

import httpx

from app.core.config import get_settings

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
# Models that exist but aren't for plain text: previews can vanish without notice.
_NOT_GENERAL = re.compile(
    r"preview|exp|image|tts|audio|live|vision|guard|robotics|learnlm|gemma|nano|lite|thinking|compound"
)


_GENERAL_GROQ = re.compile(r"gpt-oss|llama-3|llama-4|qwen|kimi|deepseek|mistral")


def _size_in_billions(name: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)b\b", name)
    return float(match.group(1)) if match else 0.0


def _version(name: str) -> tuple[float, ...]:
    return tuple(float(n) for n in re.findall(r"\d+(?:\.\d+)?", name)[:2])


def gemini_chat_candidates(models: list[dict[str, object]]) -> list[str]:
    """Flash models, newest first. Flash suits both tiers: stronger ones rarely have free quota."""
    chat = []
    for model in models:
        name = str(model.get("name", "")).removeprefix("models/")
        methods = model.get("supportedGenerationMethods") or []
        if "generateContent" in methods and "flash" in name and not _NOT_GENERAL.search(name):  # type: ignore[operator]
            chat.append(name)
    return sorted(chat, key=lambda n: (_version(n), "latest" not in n), reverse=True)


def pick_gemini(models: list[dict[str, object]]) -> dict[str, str]:
    """A first guess from the list alone. `fetch_models` then confirms chat models answer."""
    embedding = []
    for model in models:
        name = str(model.get("name", "")).removeprefix("models/")
        methods = model.get("supportedGenerationMethods") or []
        if "embedContent" in methods and "embedding" in name and not _NOT_GENERAL.search(name):  # type: ignore[operator]
            embedding.append(name)
    picked: dict[str, str] = {}
    chat = gemini_chat_candidates(models)
    if chat:
        picked |= {"GEMINI_FAST_MODEL": chat[0], "GEMINI_STRONG_MODEL": chat[0]}
    if embedding:
        picked["GEMINI_EMBEDDING_MODEL"] = max(embedding, key=_version)
    return picked


async def _answers(client: httpx.AsyncClient, key: str, model: str) -> bool:
    """Being listed isn't enough: a model can be retired for new users, or overloaded."""
    try:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key},
            json={"contents": [{"role": "user", "parts": [{"text": "Reply with: ok"}]}]},
            timeout=30,
        )
    except httpx.HTTPError:
        return False
    return response.status_code == 200


def pick_groq(ids: list[str]) -> dict[str, str]:
    picked: dict[str, str] = {}
    whisper = sorted(i for i in ids if "whisper" in i)
    if whisper:
        picked["GROQ_WHISPER_MODEL"] = next((i for i in whisper if "turbo" in i), whisper[0])
    # Only well-known general chat families: Groq also hosts speech, safety-filter and
    # single-language models that would make poor general assistants.
    chat = [
        i
        for i in ids
        if _GENERAL_GROQ.search(i) and not _NOT_GENERAL.search(i) and "safeguard" not in i
    ]
    if chat:
        by_size = sorted(chat, key=lambda i: (_size_in_billions(i), i))
        picked["GROQ_FAST_MODEL"] = by_size[0]
        picked["GROQ_STRONG_MODEL"] = by_size[-1]
    return picked


def merge_env(existing: str, picked: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Fills blanks and adds missing lines. A value already set always wins."""
    lines = existing.splitlines()
    written: dict[str, str] = {}
    for key, value in picked.items():
        for index, line in enumerate(lines):
            if line.startswith(f"{key}="):
                if not line.split("=", 1)[1].strip():
                    lines[index] = f"{key}={value}"
                    written[key] = value
                break
        else:
            lines.append(f"{key}={value}")
            written[key] = value
    return "\n".join(lines) + "\n", written


async def fetch_models() -> dict[str, str]:
    settings = get_settings()
    picked: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=20) as client:
        if settings.gemini_api_key:
            response = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
            if response.status_code == 200:
                models = response.json().get("models", [])
                picked |= pick_gemini(models)
                print("Testing Gemini models, newest first…")
                working: list[str] = []
                for candidate in gemini_chat_candidates(models)[:8]:
                    if await _answers(client, settings.gemini_api_key, candidate):
                        working.append(candidate)
                        if len(working) == 2:
                            break
                if working:
                    # The newer working model does the heavier answering work.
                    picked["GEMINI_STRONG_MODEL"] = working[0]
                    picked["GEMINI_FAST_MODEL"] = working[-1]
                else:
                    print("No Gemini chat model answered. Groq will be used until one does.")
                    picked.pop("GEMINI_FAST_MODEL", None)
                    picked.pop("GEMINI_STRONG_MODEL", None)
            else:
                print(f"Gemini refused the key (HTTP {response.status_code}).")
        else:
            print("GEMINI_API_KEY isn't in .env yet.")
        if settings.groq_api_key:
            response = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
            if response.status_code == 200:
                picked |= pick_groq([m["id"] for m in response.json().get("data", [])])
            else:
                print(f"Groq refused the key (HTTP {response.status_code}).")
        else:
            print("GROQ_API_KEY isn't in .env yet (optional: it's the fallback and transcription).")
    return picked


async def main() -> None:
    if not ENV_FILE.exists():
        sys.exit("No .env file yet. Create one first: see SETUP_KEYS.md.")
    try:
        picked = await fetch_models()
    except httpx.ConnectError:
        sys.exit(
            "Couldn't reach Gemini or Groq. Check your internet connection, and turn off any "
            "VPN or proxy, then try again. Your keys weren't the problem."
        )
    except httpx.TimeoutException:
        sys.exit("Gemini or Groq took too long to answer. Please try again in a minute.")
    updated, written = merge_env(ENV_FILE.read_text(), picked)
    ENV_FILE.write_text(updated)
    for key, value in written.items():
        print(f"Set {key}={value}")
    if not written:
        print("Nothing to change.")
    print("\nNow run: make check-ai")


if __name__ == "__main__":
    asyncio.run(main())
