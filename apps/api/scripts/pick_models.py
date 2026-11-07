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


def _version(name: str) -> tuple[float, ...]:
    return tuple(float(n) for n in re.findall(r"\d+(?:\.\d+)?", name)[:2])


def pick_gemini(models: list[dict[str, object]]) -> dict[str, str]:
    """Flash for both tiers, because stronger models often have no free quota."""
    chat, embedding = [], []
    for model in models:
        name = str(model.get("name", "")).removeprefix("models/")
        methods = model.get("supportedGenerationMethods") or []
        if "embedContent" in methods and "embedding" in name and not _NOT_GENERAL.search(name):  # type: ignore[operator]
            embedding.append(name)
        if "generateContent" in methods and "flash" in name and not _NOT_GENERAL.search(name):  # type: ignore[operator]
            chat.append(name)
    picked: dict[str, str] = {}
    if chat:
        best = max(chat, key=lambda n: (_version(n), "latest" not in n))
        picked |= {"GEMINI_FAST_MODEL": best, "GEMINI_STRONG_MODEL": best}
    if embedding:
        picked["GEMINI_EMBEDDING_MODEL"] = max(embedding, key=_version)
    return picked


def pick_groq(ids: list[str]) -> dict[str, str]:
    picked: dict[str, str] = {}
    whisper = sorted(i for i in ids if "whisper" in i)
    if whisper:
        picked["GROQ_WHISPER_MODEL"] = next((i for i in whisper if "turbo" in i), whisper[0])
    chat = [i for i in ids if "whisper" not in i and not _NOT_GENERAL.search(i)]
    fast = [i for i in chat if "instant" in i] or chat
    strong = [i for i in chat if "versatile" in i] or chat
    if fast:
        picked["GROQ_FAST_MODEL"] = sorted(fast)[0]
    if strong:
        picked["GROQ_STRONG_MODEL"] = sorted(strong)[0]
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
                picked |= pick_gemini(response.json().get("models", []))
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
