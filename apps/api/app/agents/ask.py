"""Ask Your Brain: agentic RAG.

route -> retrieve -> grade -> (rewrite and retry, at most twice) -> optional web
search. The answer is then streamed from the sources, and checked for groundedness.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.db.session import user_session
from app.guardrails.content import UNTRUSTED_SYSTEM_RULE, sanitize, wrap_untrusted
from app.providers.base import ProviderError, SearchResult
from app.providers.registry import Providers
from app.providers.structured import complete_structured
from app.services.retrieval import RetrievedChunk, SearchFilters, hybrid_search

MAX_REWRITES = 2
MAX_SOURCES = 6
_CITATION_RE = re.compile(r"\[(\d{1,2})\]")


class QueryPlan(BaseModel):
    route: Literal["saves", "web", "both", "direct"]
    search_query: str = Field(description="The question rephrased for searching")


class Grades(BaseModel):
    relevant: list[int] = Field(description="Numbers of the passages that help answer")


class Rewrite(BaseModel):
    search_query: str


class Groundedness(BaseModel):
    grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class Source:
    """One numbered source. Either a passage from a save, or a web result."""

    number: int
    kind: Literal["save", "web"]
    title: str
    text: str
    save_id: str | None = None
    start_ts: float | None = None
    url: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "kind": self.kind,
            "title": self.title,
            "snippet": self.text[:240],
            "save_id": self.save_id,
            "start_ts": self.start_ts,
            "url": self.url,
        }


@dataclass
class AskRequest:
    question: str
    user: CurrentUser
    filters: SearchFilters
    allow_web: bool = True
    history: list[dict[str, str]] = field(default_factory=list)


class AskState(TypedDict, total=False):
    request: AskRequest
    route: str
    query: str
    chunks: list[RetrievedChunk]
    relevant: list[RetrievedChunk]
    web: list[SearchResult]
    rewrites: int


def build_retrieval_graph(providers: Providers) -> Any:
    system = f"You help someone search what they saved. {UNTRUSTED_SYSTEM_RULE}"

    async def analyze_query(state: AskState) -> AskState:
        request = state["request"]
        if request.filters.save_id:
            # Chatting with one save: it always comes from that save.
            return {"route": "saves", "query": request.question, "rewrites": 0}
        plan = await complete_structured(
            providers.llm,
            "Decide how to answer this question. saves: it's about things the person saved. "
            "web: it needs current or outside information. both: it needs both. direct: "
            f"small talk needing no sources.\nQuestion: {request.question}",
            QueryPlan,
            system=system,
        )
        route = plan.route
        if not request.allow_web and route in {"web", "both"}:
            route = "saves"
        return {"route": route, "query": plan.search_query or request.question, "rewrites": 0}

    async def retrieve(state: AskState) -> AskState:
        request = state["request"]
        embedding = (await providers.embeddings.embed([state["query"]]))[0]
        async with user_session(request.user) as session:
            chunks = await _search(session, state["query"], embedding, request.filters)
        return {"chunks": chunks}

    async def grade_documents(state: AskState) -> AskState:
        chunks = state["chunks"]
        if not chunks:
            return {"relevant": []}
        listing = "\n\n".join(
            f"Passage {i + 1}:\n{wrap_untrusted(c.text[:800])}" for i, c in enumerate(chunks)
        )
        grades = await complete_structured(
            providers.llm,
            f"Which of these passages help answer: {state['request'].question!r}?\n\n{listing}",
            Grades,
            system=system,
        )
        keep = [chunks[n - 1] for n in grades.relevant if 1 <= n <= len(chunks)]
        return {"relevant": keep[:MAX_SOURCES]}

    async def rewrite_query(state: AskState) -> AskState:
        value = await complete_structured(
            providers.llm,
            f"Searching for {state['query']!r} found nothing useful. Rewrite it using different "
            f"words to answer: {state['request'].question!r}",
            Rewrite,
            system=system,
        )
        return {"query": value.search_query, "rewrites": state.get("rewrites", 0) + 1}

    async def web_search(state: AskState) -> AskState:
        try:
            return {"web": await providers.search.search(state["query"], max_results=4)}
        except ProviderError:
            return {"web": []}  # Web search is a bonus; answer from saves regardless.

    def after_route(state: AskState) -> str:
        return {"direct": END, "web": "web_search"}.get(state["route"], "retrieve")

    def after_grade(state: AskState) -> str:
        if not state["relevant"] and state.get("rewrites", 0) < MAX_REWRITES:
            return "rewrite_query"
        return "web_search" if state["route"] == "both" else END

    graph = StateGraph(AskState)
    graph.add_node("analyze_query", analyze_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("grade_documents", grade_documents)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("web_search", web_search)
    graph.add_edge(START, "analyze_query")
    graph.add_conditional_edges("analyze_query", after_route)
    graph.add_edge("retrieve", "grade_documents")
    graph.add_conditional_edges("grade_documents", after_grade)
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("web_search", END)
    return graph.compile()


async def _search(
    session: AsyncSession, query: str, embedding: list[float], filters: SearchFilters
) -> list[RetrievedChunk]:
    return await hybrid_search(session, query, embedding, filters)


def build_sources(state: AskState) -> list[Source]:
    sources: list[Source] = []
    for chunk in state.get("relevant", []):
        sources.append(
            Source(
                number=len(sources) + 1,
                kind="save",
                title=chunk.save_title or "Untitled save",
                text=chunk.text,
                save_id=str(chunk.save_id),
                start_ts=chunk.start_ts,
            )
        )
    for result in state.get("web", []):
        sources.append(
            Source(
                number=len(sources) + 1,
                kind="web",
                title=result.title,
                # Web pages are as untrusted as anything saved.
                text=sanitize(result.snippet),
                url=result.url,
            )
        )
    return sources


def answer_prompt(request: AskRequest, sources: list[Source]) -> tuple[str, str]:
    system = (
        "You answer questions about what someone has saved. Use only the numbered sources, and "
        "cite each claim like [1]. If they don't contain the answer, say so plainly rather than "
        f"guessing. {UNTRUSTED_SYSTEM_RULE}"
    )
    listing = "\n\n".join(
        f"[{s.number}] {s.title}\n{wrap_untrusted(s.text[:1600])}" for s in sources
    )
    recent = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in request.history[-6:])
    context = f"Conversation so far:\n{recent}\n\n" if recent else ""
    if not sources:
        return (
            f"{context}Question: {request.question}\n\nNo saved sources matched. Say that "
            "nothing they've saved covers this, and suggest what they could save or ask.",
            system,
        )
    return f"{context}Sources:\n{listing}\n\nQuestion: {request.question}", system


def used_citations(answer: str, sources: list[Source]) -> list[dict[str, Any]]:
    """Only sources the answer actually cites, and never a number it made up."""
    cited = {int(number) for number in _CITATION_RE.findall(answer)}
    return [source.public() for source in sources if source.number in cited]


async def check_groundedness(
    providers: Providers, answer: str, sources: list[Source]
) -> Groundedness:
    if not sources:
        return Groundedness(grounded=True)
    listing = "\n\n".join(f"[{s.number}] {wrap_untrusted(s.text[:1000])}" for s in sources)
    try:
        return await complete_structured(
            providers.llm,
            f"Check this answer against its sources. List any claim the sources don't support."
            f"\n\nAnswer:\n{answer}\n\nSources:\n{listing}",
            Groundedness,
            system=UNTRUSTED_SYSTEM_RULE,
        )
    except ProviderError:
        # We couldn't check it, so don't claim it's verified either way.
        return Groundedness(grounded=False, unsupported_claims=[])
