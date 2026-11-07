"""Measures the AI against labeled data, on the real providers. Needs API keys.

Run with `make eval`. Writes `evals/results.md`. Nothing here is ever hand-written:
if the file doesn't exist, the evals haven't been run, and no numbers should be quoted.
"""

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.agents.ingestion import ActionPlan, Classification
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, wrap_untrusted
from app.providers.base import ModelTier, ProviderError
from app.providers.registry import Providers, get_providers
from app.providers.structured import complete_structured
from app.services.link_verification import domain_of, resolve_entity

DATA = Path(__file__).parent / "datasets"
# The free tiers throttle hard, so evals run slowly on purpose.
PAUSE_SECONDS = 4.0


def load(name: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (DATA / name).read_text().splitlines() if line.strip()]


class Judgement(BaseModel):
    faithful: bool = Field(description="Every claim is supported by the context")
    relevant: bool = Field(description="It answers the question asked")


async def each(
    items: list[dict[str, Any]], run: Callable[[dict[str, Any]], Awaitable[None]]
) -> int:
    """Runs every item, counting provider failures rather than scoring them as wrong."""
    errors = 0
    for item in items:
        try:
            await run(item)
        except ProviderError as error:
            errors += 1
            print(f"  provider error: {error}", file=sys.stderr)
        await asyncio.sleep(PAUSE_SECONDS)
    return errors


async def eval_classification(providers: Providers) -> dict[str, Any]:
    items = load("classification.jsonl")
    correct = 0

    async def run(item: dict[str, Any]) -> None:
        nonlocal correct
        result = await complete_structured(
            providers.llm,
            "Classify this content. mode: study is for learning material, work is for "
            "professional material such as meetings and client email, life is everything "
            f"else.\n\n{wrap_untrusted(item['text'])}",
            Classification,
            system=UNTRUSTED_SYSTEM_RULE,
        )
        correct += result.mode == item["mode"]

    errors = await each(items, run)
    scored = len(items) - errors
    return {
        "metric": "Classification accuracy (life/study/work)",
        "value": correct / scored if scored else None,
        "n": scored,
        "errors": errors,
    }


async def eval_links(providers: Providers) -> dict[str, Any]:
    items = load("entity_links.jsonl")
    correct = 0

    async def run(item: dict[str, Any]) -> None:
        nonlocal correct
        resource = await resolve_entity(
            name=item["name"],
            entity_type=item["type"],
            context=item["context"],
            search=providers.search,
            llm=providers.llm,
            system=UNTRUSTED_SYSTEM_RULE,
        )
        if resource and resource.verified:
            domain = domain_of(resource.url)
            correct += domain == item["domain"] or domain.endswith(f".{item['domain']}")

    errors = await each(items, run)
    scored = len(items) - errors
    return {
        "metric": "Entity to official link accuracy",
        "value": correct / scored if scored else None,
        "n": scored,
        "errors": errors,
    }


def _matched(expected: str, found: list[str]) -> bool:
    words = {word for word in expected.lower().split() if len(word) > 3}
    return any(
        len(words & set(title.lower().split())) >= max(1, len(words) // 2) for title in found
    )


async def eval_actions(providers: Providers) -> dict[str, Any]:
    items = load("actions.jsonl")
    true_positive = extracted = expected = 0

    async def run(item: dict[str, Any]) -> None:
        nonlocal true_positive, extracted, expected
        plan = await complete_structured(
            providers.llm,
            "Extract the concrete tasks this content calls for. Include only what the content "
            f"supports.\n\n{wrap_untrusted(item['text'])}",
            ActionPlan,
            system=UNTRUSTED_SYSTEM_RULE,
        )
        titles = [action.title for action in plan.actions]
        extracted += len(titles)
        expected += len(item["actions"])
        true_positive += sum(_matched(action, titles) for action in item["actions"])

    errors = await each(items, run)
    precision = true_positive / extracted if extracted else None
    recall = true_positive / expected if expected else None
    return {
        "metric": "Action extraction",
        "value": precision,
        "recall": recall,
        "n": len(items) - errors,
        "errors": errors,
    }


async def eval_rag(providers: Providers) -> dict[str, Any]:
    """Judges answers given known context. An LLM grades them, so treat this as indicative."""
    items = load("rag.jsonl")
    faithful = relevant = 0

    async def run(item: dict[str, Any]) -> None:
        nonlocal faithful, relevant
        answer = await providers.llm.complete(
            f"Sources:\n[1] {wrap_untrusted(item['context'])}\n\nQuestion: {item['question']}",
            system=(
                "Answer using only the sources, citing them like [1]. If they don't contain the "
                f"answer, say so plainly. {UNTRUSTED_SYSTEM_RULE}"
            ),
            tier=ModelTier.STRONG,
        )
        judged = await complete_structured(
            providers.llm,
            f"Question: {item['question']}\nContext: {wrap_untrusted(item['context'])}\n"
            f"Answer to judge: {wrap_untrusted(answer)}\nJudge this answer.",
            Judgement,
            system=UNTRUSTED_SYSTEM_RULE,
        )
        faithful += judged.faithful
        relevant += judged.relevant

    errors = await each(items, run)
    scored = len(items) - errors
    return {
        "metric": "RAG faithfulness (LLM-judged)",
        "value": faithful / scored if scored else None,
        "relevance": relevant / scored if scored else None,
        "n": scored,
        "errors": errors,
    }


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def render(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Eval results",
        "",
        f"Generated by `make eval` on {datetime.now(UTC).date().isoformat()}. Small datasets, so "
        "treat these as indicative. RAG scores are judged by a model.",
        "",
        "| Metric | Result | Items | Provider errors |",
        "|---|---|---|---|",
    ]
    for result in results:
        value = percent(result["value"])
        if "recall" in result:
            value = f"precision {value}, recall {percent(result['recall'])}"
        if "relevance" in result:
            value = f"{value} (answer relevance {percent(result['relevance'])})"
        lines.append(f"| {result['metric']} | {value} | {result['n']} | {result['errors']} |")
    return "\n".join(lines) + "\n"


async def main() -> None:
    providers = get_providers()
    results = []
    for name, evaluate in [
        ("classification", eval_classification),
        ("actions", eval_actions),
        ("RAG", eval_rag),
        ("links", eval_links),
    ]:
        print(f"Running {name}…", file=sys.stderr)
        results.append(await evaluate(providers))
    report = render(results)
    print(report)
    (Path(__file__).parent / "results.md").write_text(report)


if __name__ == "__main__":
    asyncio.run(main())
