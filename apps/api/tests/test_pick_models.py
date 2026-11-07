from scripts.pick_models import merge_env, pick_gemini, pick_groq


def _gemini(name: str, *methods: str) -> dict[str, object]:
    return {"name": f"models/{name}", "supportedGenerationMethods": list(methods)}


def test_gemini_prefers_the_newest_stable_flash_and_embedding() -> None:
    picked = pick_gemini(
        [
            _gemini("gemini-2.5-flash", "generateContent"),
            _gemini("gemini-3.0-flash", "generateContent"),
            _gemini("gemini-4.0-flash-preview", "generateContent"),
            _gemini("gemini-4.0-flash-image", "generateContent"),
            _gemini("gemini-3.0-pro", "generateContent"),
            _gemini("gemini-embedding-001", "embedContent"),
            _gemini("gemini-embedding-002", "embedContent"),
        ]
    )
    assert picked["GEMINI_FAST_MODEL"] == "gemini-3.0-flash"
    assert picked["GEMINI_STRONG_MODEL"] == "gemini-3.0-flash"
    assert picked["GEMINI_EMBEDDING_MODEL"] == "gemini-embedding-002"


def test_groq_picks_by_purpose() -> None:
    picked = pick_groq(
        ["whisper-large-v3", "whisper-large-v3-turbo", "llama-3.1-8b-instant",
         "llama-3.3-70b-versatile", "meta-llama/llama-guard-4"]
    )  # fmt: skip
    assert picked == {
        "GROQ_WHISPER_MODEL": "whisper-large-v3-turbo",
        "GROQ_FAST_MODEL": "llama-3.1-8b-instant",
        "GROQ_STRONG_MODEL": "llama-3.3-70b-versatile",
    }


def test_groq_skips_speech_safety_and_single_language_models() -> None:
    picked = pick_groq(
        ["allam-2-7b", "canopylabs/orpheus-v1-english", "meta-llama/llama-prompt-guard-2-86m",
         "openai/gpt-oss-safeguard-20b", "openai/gpt-oss-20b", "openai/gpt-oss-120b",
         "qwen/qwen3.8-27b", "whisper-large-v3-turbo"]
    )  # fmt: skip
    assert picked["GROQ_FAST_MODEL"] == "openai/gpt-oss-20b"
    assert picked["GROQ_STRONG_MODEL"] == "openai/gpt-oss-120b"


def test_merge_fills_blanks_adds_missing_and_never_overwrites() -> None:
    updated, written = merge_env(
        "A_KEY=secret\nGEMINI_FAST_MODEL=\nGEMINI_STRONG_MODEL=my-choice\n",
        {"GEMINI_FAST_MODEL": "x", "GEMINI_STRONG_MODEL": "y", "GROQ_FAST_MODEL": "z"},
    )
    assert "GEMINI_FAST_MODEL=x" in updated
    assert "GEMINI_STRONG_MODEL=my-choice" in updated
    assert "GROQ_FAST_MODEL=z" in updated
    assert "A_KEY=secret" in updated
    assert written == {"GEMINI_FAST_MODEL": "x", "GROQ_FAST_MODEL": "z"}
