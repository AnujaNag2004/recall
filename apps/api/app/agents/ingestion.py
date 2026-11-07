"""The ingestion graph: turns a raw save into an understood Smart Card.

Each node is small, reports its stage (which the UI streams live), and returns only
the state it changed. Database access and providers are injected, so nodes can be
tested without a network.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, sanitize, wrap_untrusted
from app.providers.base import ProviderError, TranscriptSegment
from app.providers.registry import Providers
from app.providers.structured import complete_structured
from app.services.chunking import Chunk, chunk_text, chunk_transcript
from app.services.content import FetchedContent, UnreadableSourceError
from app.services.link_verification import VerifiedResource, resolve_entity

logger = logging.getLogger(__name__)

# What a model sees of a long source. Embedding still covers the whole text.
MODEL_CONTEXT_CHARS = 30_000
EMBED_BATCH = 50
# Each entity costs a search and a model call, so free tiers need a ceiling.
MAX_ENTITIES = 10
INTENTS = ["learn", "try", "buy", "cook", "do at work", "reference", "just vibes"]

Template = Literal["recipe", "workout", "study", "meeting", "product", "generic"]


class Classification(BaseModel):
    mode: Literal["life", "study", "work"]
    content_template: Template
    language: str = Field(description="ISO 639-1 code of the content's language")


class Summary(BaseModel):
    title: str = Field(description="A short descriptive title, under 80 characters")
    tldr: str = Field(description="Two or three plain sentences")
    key_points: list[str] = Field(description="Three to six takeaways, one sentence each")


EntityType = Literal[
    "tool", "website", "book", "course", "product", "repo", "place", "person", "other"
]


class Entity(BaseModel):
    name: str
    type: EntityType
    context: str = Field(description="The phrase where it's mentioned")
    mention_seconds: float | None = Field(
        default=None, description="Timestamp if it appears next to a [m:ss] marker"
    )


class EntityList(BaseModel):
    entities: list[Entity]


class PlannedAction(BaseModel):
    title: str = Field(description="A short imperative task")
    description: str | None = None
    type: Literal["action_item", "checklist_item"] = "checklist_item"
    owner: str | None = Field(default=None, description="Who it's assigned to, if stated")
    due: str | None = Field(default=None, description="ISO date, only if clearly stated")


class ActionPlan(BaseModel):
    actions: list[PlannedAction]


class TopicAssignment(BaseModel):
    topics: list[str] = Field(description="One to three short topic names")


class InferredIntent(BaseModel):
    intent: Literal["learn", "try", "buy", "cook", "do at work", "reference", "just vibes"]


class MicroCommitment(BaseModel):
    title: str = Field(description="The smallest concrete first step, doable in minutes")
    size: Literal["tiny", "small"] = "tiny"
    hours_from_now: int = Field(ge=1, le=168, description="A sensible time to do it")


class IngestionState(TypedDict, total=False):
    save_id: UUID
    source_type: str
    source_url: str | None
    storage_path: str | None
    raw_text: str | None
    user_title: str | None
    content: FetchedContent
    text: str
    classification: Classification
    summary: Summary
    intent: str | None


class IngestionStore(Protocol):
    """Everything the graph needs to persist."""

    async def set_stage(self, save_id: UUID, stage: str) -> None: ...
    async def save_content(self, save_id: UUID, content: FetchedContent, text: str) -> None: ...
    async def save_classification(self, save_id: UUID, value: Classification) -> None: ...
    async def save_summary(self, save_id: UUID, value: Summary, keep_title: bool) -> None: ...
    async def save_chunks(
        self, save_id: UUID, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None: ...
    async def save_entity(
        self, save_id: UUID, entity: Entity, resource: VerifiedResource | None
    ) -> None: ...
    async def clear_derived(self, save_id: UUID) -> None: ...
    async def save_action(self, save_id: UUID, action: PlannedAction) -> None: ...
    async def existing_topics(self, save_id: UUID) -> list[str]: ...
    async def save_topics(self, save_id: UUID, topics: list[str]) -> None: ...
    async def save_inferred_intent(self, save_id: UUID, intent: str) -> None: ...
    async def save_micro_commitment(
        self, save_id: UUID, value: MicroCommitment, scheduled_for: datetime
    ) -> None: ...
    async def finish(self, save_id: UUID) -> None: ...


class ContentReader(Protocol):
    async def read(self, state: IngestionState) -> FetchedContent: ...


@dataclass(frozen=True)
class IngestionDeps:
    providers: Providers
    store: IngestionStore
    reader: ContentReader
    settings: Settings


def build_ingestion_graph(deps: IngestionDeps) -> Any:
    providers, store = deps.providers, deps.store
    system = f"You analyze content a person saved. {UNTRUSTED_SYSTEM_RULE}"

    async def fetch_content(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Reading the source")
        content = await deps.reader.read(state)
        if not content.text.strip():
            raise UnreadableSourceError("We couldn't find any content in that.")
        content.text = content.text[: deps.settings.max_content_chars]
        return {"content": content}

    async def sanitize_content(state: IngestionState) -> IngestionState:
        content = state["content"]
        # What models read is cleaned, and what we store for the reader view is too.
        text = sanitize(content.text)
        content.transcript = [
            TranscriptSegment(s.start, s.end, sanitize(s.text)) for s in content.transcript
        ]
        await store.save_content(state["save_id"], content, text)
        return {"text": text, "content": content}

    async def classify(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Working out what this is")
        prompt = (
            "Classify this content. mode: study is for learning material, work is for "
            "professional material such as meetings and client email, life is everything "
            "else. content_template picks the best fitting card layout.\n\n"
            f"{wrap_untrusted(state['text'][:6000])}"
        )
        value = await complete_structured(providers.llm, prompt, Classification, system=system)
        await store.save_classification(state["save_id"], value)
        return {"classification": value}

    async def summarize(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Writing the summary")
        prompt = (
            "Summarize this for the person who saved it. Use only what the content says.\n\n"
            f"{wrap_untrusted(state['text'][:MODEL_CONTEXT_CHARS])}"
        )
        value = await complete_structured(providers.llm, prompt, Summary, system=system)
        keep_title = bool(state.get("user_title") or state["content"].title)
        await store.save_summary(state["save_id"], value, keep_title)
        return {"summary": value}

    async def chunk_and_embed(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Making it searchable")
        transcript = state["content"].transcript
        chunks = chunk_transcript(transcript) if transcript else chunk_text(state["text"])
        embeddings: list[list[float]] = []
        for start in range(0, len(chunks), EMBED_BATCH):
            batch = [chunk.text for chunk in chunks[start : start + EMBED_BATCH]]
            embeddings.extend(await providers.embeddings.embed(batch))
        await store.save_chunks(state["save_id"], chunks, embeddings)
        return {}

    async def extract_entities_and_resources(state: IngestionState) -> IngestionState:
        save_id = state["save_id"]
        await store.set_stage(save_id, "Finding tools and resources")
        await store.clear_derived(save_id)
        prompt = (
            "List every specific tool, website, book, course, product, code repository, place "
            "or person this content mentions by name. Skip generic concepts.\n\n"
            f"{wrap_untrusted(_with_timestamps(state)[:MODEL_CONTEXT_CHARS])}"
        )
        found = await complete_structured(providers.llm, prompt, EntityList, system=system)
        seen: set[str] = set()
        for entity in found.entities:
            key = entity.name.strip().lower()
            if not key or key in seen or len(seen) >= MAX_ENTITIES:
                continue
            seen.add(key)
            resource = None
            if entity.type != "other":
                try:
                    resource = await resolve_entity(
                        name=entity.name,
                        entity_type=entity.type,
                        context=entity.context,
                        search=providers.search,
                        llm=providers.llm,
                        system=system,
                    )
                except ProviderError as error:
                    logger.warning("Could not resolve an entity: %s", error)
            await store.save_entity(save_id, entity, resource)
        return {}

    async def extract_actions(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Planning what to do")
        template = state["classification"].content_template
        guidance = {
            "recipe": "an ingredient checklist, one ingredient per item",
            "workout": "a plan listing each exercise with its sets and reps",
            "study": "a short study schedule of concrete study tasks",
            "meeting": "action items, with the owner and due date where they're stated",
            "product": "the steps to evaluate or buy it",
            "generic": "a few concrete things worth doing, or none if nothing is actionable",
        }[template]
        prompt = (
            f"Extract {guidance}. Include only what the content supports. Most content "
            "deserves fewer than eight items.\n\n"
            f"{wrap_untrusted(state['text'][:MODEL_CONTEXT_CHARS])}"
        )
        plan = await complete_structured(providers.llm, prompt, ActionPlan, system=system)
        for action in plan.actions[:15]:
            await store.save_action(state["save_id"], action)
        return {}

    async def curate(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Connecting it to your other saves")
        existing = await store.existing_topics(state["save_id"])
        prompt = (
            "Assign this content one to three broad topics. Reuse an existing topic whenever "
            f"one fits. Existing topics: {json.dumps(existing[:200])}\n\n"
            f"Summary: {wrap_untrusted(state['summary'].tldr)}"
        )
        value = await complete_structured(providers.llm, prompt, TopicAssignment, system=system)
        await store.save_topics(state["save_id"], value.topics[:3])
        return {}

    async def infer_intent(state: IngestionState) -> IngestionState:
        if state.get("intent"):
            return {}
        prompt = (
            "Why would someone most likely save this? Pick the closest intent.\n\n"
            f"{wrap_untrusted(state['summary'].tldr)}"
        )
        value = await complete_structured(providers.llm, prompt, InferredIntent, system=system)
        await store.save_inferred_intent(state["save_id"], value.intent)
        return {"intent": value.intent}

    async def micro_commitment(state: IngestionState) -> IngestionState:
        await store.set_stage(state["save_id"], "Choosing a small first step")
        if state.get("intent") == "just vibes":
            return {}  # They told us there's nothing to do, so we don't invent a chore.
        prompt = (
            f"The person saved this because of this intent: {state.get('intent')}. Propose the "
            "smallest concrete first step, something taking minutes rather than hours, and a "
            f"sensible time for it.\n\n{wrap_untrusted(state['summary'].tldr)}"
        )
        value = await complete_structured(providers.llm, prompt, MicroCommitment, system=system)
        when = datetime.now(UTC) + timedelta(hours=value.hours_from_now)
        await store.save_micro_commitment(state["save_id"], value, when)
        return {}

    def optional(name: str, node: Any) -> Any:
        """Extras shouldn't cost someone their whole save if a service is having a bad day."""

        async def run(state: IngestionState) -> IngestionState:
            try:
                result: IngestionState = await node(state)
                return result
            except ProviderError as error:
                logger.warning("Optional step %s skipped: %s", name, error)
                return {}

        return run

    async def finalize(state: IngestionState) -> IngestionState:
        await store.finish(state["save_id"])
        return {}

    graph = StateGraph(IngestionState)
    steps = [
        ("fetch_content", fetch_content),
        ("guardrail_sanitize", sanitize_content),
        ("classify", classify),
        ("summarize", summarize),
        ("chunk_and_embed", chunk_and_embed),
        ("extract_entities", optional("entities", extract_entities_and_resources)),
        ("extract_actions", optional("actions", extract_actions)),
        ("curate", optional("topics", curate)),
        ("infer_intent", optional("intent", infer_intent)),
        ("micro_commitment", optional("micro-commitment", micro_commitment)),
        ("finalize", finalize),
    ]
    previous: str = START
    for name, node in steps:
        graph.add_node(name, node)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()


def _with_timestamps(state: IngestionState) -> str:
    transcript = state["content"].transcript
    if not transcript:
        return state["text"]
    return "\n".join(f"[{int(s.start) // 60}:{int(s.start) % 60:02d}] {s.text}" for s in transcript)


def vector_literal(values: list[float]) -> str:
    return json.dumps(values, separators=(",", ":"))
