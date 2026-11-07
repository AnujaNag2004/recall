"""Ask Your Brain, Learn Mode, the graph, scheduled agents and limits."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.agents.ask import Source, used_citations
from app.agents.scheduled import (
    run_adapt_tasks,
    run_just_in_time_recall,
    run_link_health,
    run_weekly_insights,
)
from app.core.config import Settings, get_settings
from app.providers.registry import get_providers
from app.routers.insights import classify_topics
from app.services.retrieval import rrf_fuse
from app.services.srs import sm2
from tests.conftest import auth_header, create_user
from tests.fakes import FakeLLM, fake_providers
from tests.test_ingestion import create_note, drain_jobs


def parse_events(body: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


@pytest.fixture
async def workspace(client: AsyncClient, postgres: Any) -> tuple[str, dict[str, str]]:
    headers = auth_header(create_user(postgres))
    me = (await client.get("/api/v1/me", headers=headers)).json()
    return me["workspaces"][0]["id"], headers


@pytest.fixture
def use_fakes(app: FastAPI) -> FakeLLM:
    llm = FakeLLM()
    app.dependency_overrides[get_providers] = lambda: fake_providers(llm=llm)
    return llm


async def ask(client: AsyncClient, workspace: Any, **body: Any) -> list[dict[str, Any]]:
    response = await client.post(
        f"/api/v1/workspaces/{workspace[0]}/ask", headers=workspace[1], json=body
    )
    assert response.status_code == 200, response.text
    return parse_events(response.text)


async def test_answers_cite_the_saves_they_came_from(
    client: AsyncClient, settings: Settings, workspace: Any, use_fakes: FakeLLM
) -> None:
    save_id = await create_note(client, workspace)
    await drain_jobs(settings)
    events = await ask(client, workspace, message="How do I find shortest paths?")
    kinds = [event["type"] for event in events]
    assert kinds[0] == "conversation"
    assert "token" in kinds
    done = events[-1]
    assert done["type"] == "done"
    assert done["grounded"] is True
    assert [c["save_id"] for c in done["citations"]] == [save_id]
    answer = "".join(e["text"] for e in events if e["type"] == "token")
    assert "[1]" in answer


async def test_the_conversation_is_saved_and_continued(
    client: AsyncClient, settings: Settings, workspace: Any, use_fakes: FakeLLM
) -> None:
    await create_note(client, workspace)
    await drain_jobs(settings)
    first = await ask(client, workspace, message="First question?")
    conversation_id = first[0]["conversation_id"]
    second = await ask(client, workspace, message="Follow up?", conversation_id=conversation_id)
    assert second[0]["conversation_id"] == conversation_id
    messages = (
        await client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=workspace[1])
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[1]["citations"]
    assert "First question?" in use_fakes.prompts[-3] or any(
        "First question?" in p for p in use_fakes.prompts
    )


async def test_weak_retrieval_rewrites_and_then_admits_it_found_nothing(
    client: AsyncClient, settings: Settings, workspace: Any, app: FastAPI
) -> None:
    llm = FakeLLM(
        {"Which of these passages": {"relevant": []}, "found nothing useful": {"search_query": "x"}}
    )
    app.dependency_overrides[get_providers] = lambda: fake_providers(llm=llm)
    await create_note(client, workspace)
    await drain_jobs(settings)
    events = await ask(client, workspace, message="Something unrelated?")
    assert sum("found nothing useful" in prompt for prompt in llm.prompts) == 2  # The retry cap.
    assert next(e for e in events if e["type"] == "sources")["sources"] == []
    assert any("No saved sources matched" in prompt for prompt in llm.prompts)


async def test_conversations_are_private(
    client: AsyncClient, settings: Settings, workspace: Any, use_fakes: FakeLLM, postgres: Any
) -> None:
    await create_note(client, workspace)
    await drain_jobs(settings)
    events = await ask(client, workspace, message="Mine?")
    conversation_id = events[0]["conversation_id"]
    outsider = auth_header(create_user(postgres))
    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=outsider
    )
    assert response.status_code == 404


async def test_per_save_chat_stays_on_that_save(
    client: AsyncClient, settings: Settings, workspace: Any, use_fakes: FakeLLM
) -> None:
    await create_note(client, workspace)
    other = await create_note(client, workspace)
    await drain_jobs(settings)
    response = await client.post(
        f"/api/v1/saves/{other}/chat", headers=workspace[1], json={"message": "What's this about?"}
    )
    events = parse_events(response.text)
    sources = next(e for e in events if e["type"] == "sources")["sources"]
    assert {s["save_id"] for s in sources} == {other}


def test_citations_only_include_sources_actually_cited() -> None:
    sources = [Source(1, "save", "A", "a"), Source(2, "save", "B", "b")]
    cited = used_citations("True [2], and also [7].", sources)
    assert [c["number"] for c in cited] == [2]


def test_rrf_rewards_appearing_in_both_lists() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    scores = rrf_fuse([[a, b], [c, b]])
    assert max(scores, key=lambda key: scores[key]) == b


NOW = datetime(2026, 11, 7, tzinfo=UTC)


def review(grade: int, ease: float = 2.5, interval: int = 0, reps: int = 0) -> Any:
    return sm2(ease=ease, interval_days=interval, repetitions=reps, grade=grade, now=NOW)


def test_sm2_first_two_intervals_are_one_then_six_days() -> None:
    assert review(5).interval_days == 1
    assert review(5, interval=1, reps=1).interval_days == 6


def test_sm2_later_intervals_grow_by_ease() -> None:
    assert review(5, ease=2.5, interval=6, reps=2).interval_days == 15


def test_sm2_a_lapse_restarts_the_card() -> None:
    result = review(2, interval=30, reps=5)
    assert (result.interval_days, result.repetitions) == (1, 0)
    assert result.due_at == NOW + timedelta(days=1)


def test_sm2_ease_never_falls_below_the_floor() -> None:
    assert review(0, ease=1.3).ease == 1.3


def test_sm2_rejects_invalid_grades() -> None:
    with pytest.raises(ValueError):
        review(6)


async def test_flashcards_from_generation_to_review(
    client: AsyncClient, settings: Settings, workspace: Any, use_fakes: FakeLLM
) -> None:
    workspace_id, headers = workspace
    save_id = await create_note(client, workspace)
    await drain_jobs(settings)
    created = await client.post(f"/api/v1/saves/{save_id}/flashcards", headers=headers)
    assert created.status_code == 201
    card = created.json()[0]
    queue = await client.get(f"/api/v1/workspaces/{workspace_id}/learn/queue", headers=headers)
    assert [c["id"] for c in queue.json()] == [card["id"]]

    reviewed = await client.post(
        f"/api/v1/flashcards/{card['id']}/review", headers=headers, json={"grade": 5}
    )
    assert reviewed.json()["interval_days"] == 1
    queue = await client.get(f"/api/v1/workspaces/{workspace_id}/learn/queue", headers=headers)
    assert queue.json() == []


async def test_a_quiz_drops_questions_with_impossible_answers(
    client: AsyncClient, settings: Settings, workspace: Any, app: FastAPI
) -> None:
    llm = FakeLLM(
        {"Write a quiz": {"questions": [
            {"question": "ok", "options": ["a", "b"], "answer_index": 1},
            {"question": "bad", "options": ["a", "b"], "answer_index": 5},
        ]}}
    )  # fmt: skip
    app.dependency_overrides[get_providers] = lambda: fake_providers(llm=llm)
    save_id = await create_note(client, workspace)
    await drain_jobs(settings)
    quiz = await client.post(f"/api/v1/saves/{save_id}/quiz", headers=workspace[1])
    assert [q["question"] for q in quiz.json()["questions"]] == ["ok"]


def test_topic_flags() -> None:
    flags = classify_topics([(10, 1), (1, 0), (1, 1), (4, 0)])
    assert flags[0][0] is True  # Far above the typical topic.
    assert flags[1] == (False, False)  # One save isn't a pattern.
    assert flags[3][1] is True  # Saved repeatedly, never acted on.


async def test_graph_has_topics_from_ingestion(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    await create_note(client, workspace)
    await drain_jobs(settings)
    graph = await client.get(f"/api/v1/workspaces/{workspace[0]}/graph", headers=workspace[1])
    assert [n["name"] for n in graph.json()["nodes"]] == ["Algorithms"]


async def test_cron_needs_the_secret(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(cron_secret="right")
    assert (await client.post("/internal/cron/hourly")).status_code == 401
    wrong = await client.post("/internal/cron/hourly", headers={"x-cron-secret": "wrong"})
    assert wrong.status_code == 401
    good = await client.post("/internal/cron/hourly", headers={"x-cron-secret": "right"})
    assert good.status_code == 202
    missing = await client.post("/internal/cron/nope", headers={"x-cron-secret": "right"})
    assert missing.status_code == 404


async def test_an_unset_cron_secret_locks_the_route(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(cron_secret=None)
    response = await client.post("/internal/cron/hourly", headers={"x-cron-secret": ""})
    assert response.status_code == 401


async def test_recall_makes_one_card_for_an_upcoming_event(
    client: AsyncClient, settings: Settings, workspace: Any, postgres: Any, app: FastAPI
) -> None:
    workspace_id, headers = workspace
    await create_note(client, workspace)
    await drain_jobs(settings)
    user = (await client.get("/api/v1/me", headers=headers)).json()["user"]["id"]
    postgres.psql(
        "insert into public.calendar_events (workspace_id, user_id, title, starts_at) values "
        f"('{workspace_id}', '{user}', 'Graphs and cycles exam', now() + interval '3 hours');"
    )
    providers = fake_providers(llm=FakeLLM({"Coming up": {"summary": "Revise cycles first."}}))
    assert await run_just_in_time_recall(providers) == 1
    assert await run_just_in_time_recall(providers) == 0  # No duplicates on the next hour.
    home = (await client.get(f"/api/v1/workspaces/{workspace_id}/home", headers=headers)).json()
    assert home["recall_cards"][0]["body"] == "Revise cycles first."
    card_id = home["recall_cards"][0]["id"]
    assert (
        await client.post(f"/api/v1/recall-cards/{card_id}/dismiss", headers=headers)
    ).status_code == 204
    home = (await client.get(f"/api/v1/workspaces/{workspace_id}/home", headers=headers)).json()
    assert home["recall_cards"] == []


async def test_a_repeatedly_skipped_task_gets_smaller(
    client: AsyncClient, workspace: Any, postgres: Any
) -> None:
    workspace_id, headers = workspace
    created = await client.post(
        f"/api/v1/workspaces/{workspace_id}/tasks", headers=headers, json={"title": "Read the book"}
    )
    task_id = created.json()["id"]
    for _ in range(2):
        await client.post(
            f"/api/v1/tasks/{task_id}/respond", headers=headers, json={"answer": "not_yet"}
        )
    providers = fake_providers(llm=FakeLLM({"keeps getting put off": {"title": "Open to page 1"}}))
    assert await run_adapt_tasks(providers) >= 1
    tasks = await client.get(f"/api/v1/workspaces/{workspace_id}/tasks", headers=headers)
    assert tasks.json()[0]["title"] == "Open to page 1"
    assert tasks.json()[0]["size"] == "tiny"


async def test_weekly_insights_are_written_and_honest_about_empty_weeks(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    workspace_id, headers = workspace
    llm = FakeLLM()
    await run_weekly_insights(fake_providers(llm=llm))
    assert (
        await client.get(f"/api/v1/workspaces/{workspace_id}/insights", headers=headers)
    ).json() == []

    await create_note(client, workspace)
    await drain_jobs(settings)
    await run_weekly_insights(fake_providers(llm=llm))
    insights = (
        await client.get(f"/api/v1/workspaces/{workspace_id}/insights", headers=headers)
    ).json()
    assert {i["kind"] for i in insights} == {"weekly_digest", "reflection"}


async def test_link_health_unverifies_dead_links(
    client: AsyncClient, settings: Settings, workspace: Any, postgres: Any
) -> None:
    save_id = await create_note(client, workspace)
    await drain_jobs(settings)
    postgres.psql(
        "insert into public.resources (save_id, url, domain, confidence, verified) values "
        f"('{save_id}', 'http://127.0.0.1/dead', '127.0.0.1', 0.9, true);"
    )
    assert await run_link_health() >= 1
    result = postgres.psql(f"select verified from public.resources where save_id = '{save_id}';")
    assert " f\n" in result


async def test_the_daily_ai_cap_is_enforced(
    app: FastAPI, client: AsyncClient, workspace: Any, settings: Settings
) -> None:
    capped = settings.model_copy(update={"daily_ai_usage_cap": 1})
    app.dependency_overrides[get_settings] = lambda: capped
    url = f"/api/v1/workspaces/{workspace[0]}/saves"
    first = await client.post(url, headers=workspace[1], json={"text": "one note"})
    assert first.status_code == 201
    second = await client.post(url, headers=workspace[1], json={"text": "two note"})
    assert second.status_code == 429
    assert "limit" in second.json()["detail"]


async def test_the_rate_limit_is_enforced(
    app: FastAPI, client: AsyncClient, workspace: Any, settings: Settings
) -> None:
    tight = settings.model_copy(update={"rate_limit_per_minute": 1})
    app.dependency_overrides[get_settings] = lambda: tight
    url = f"/api/v1/workspaces/{workspace[0]}/saves"
    statuses = [
        (await client.post(url, headers=workspace[1], json={"text": "n"})).status_code
        for _ in range(3)
    ]
    assert 429 in statuses
