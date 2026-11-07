"""Structured model output: validated with Pydantic, retried once with the error."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider, ModelTier, ProviderError

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(ProviderError):
    """The model's output failed validation twice."""


def _parse(raw: str, schema: type[T]) -> T:
    text = raw.strip()
    # Some models wrap JSON in a Markdown fence even in JSON mode.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    return schema.model_validate(json.loads(text))


async def complete_structured(
    llm: LLMProvider,
    prompt: str,
    schema: type[T],
    *,
    system: str | None = None,
    tier: ModelTier = ModelTier.FAST,
) -> T:
    shape = json.dumps(schema.model_json_schema())
    full_prompt = f"{prompt}\n\nRespond with only JSON matching this JSON Schema:\n{shape}"
    raw = await llm.complete(full_prompt, system=system, tier=tier, json_mode=True)
    try:
        return _parse(raw, schema)
    except (ValueError, ValidationError) as error:
        retry = (
            f"{full_prompt}\n\nYour previous response was invalid: {str(error)[:500]}\n"
            "Respond again with only valid JSON."
        )
        raw = await llm.complete(retry, system=system, tier=tier, json_mode=True)
        try:
            return _parse(raw, schema)
        except (ValueError, ValidationError) as second_error:
            raise StructuredOutputError("Model output failed validation") from second_error
