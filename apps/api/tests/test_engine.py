"""The Save-to-Action loop end to end, plus its score logic."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security import CurrentUser
from app.db.session import user_session
from app.services.metrics import (
    SaveFacts,
    by_category,
    compute_score,
    compute_streak,
)
from app.services.retrieval import SearchFilters, hybrid_search
from tests.conftest import auth_header, create_team, create_user
from tests.fakes import FakeEmbeddings
from tests.test_ingestion import create_note, drain_jobs

NOW = datetime(2026, 11, 7, tzinfo=UTC)


def facts(*statuses: str, intent: str | None = "learn") -> SaveFacts:
    return SaveFacts(uuid4(), intent, NOW, statuses)


def test_a_save_counts_once_any_task_is_done() -> None:
    assert compute_score([facts("done", "skipped"), facts("accepted"), facts()]) == {
        "acted": 1, "total": 3, "ratio": 0.333,
    }  # fmt: skip


def test_letting_go_raises_the_score_rather_than_lowering_it() -> None:
    before = compute_score([facts("done"), facts("accepted")])["ratio"]
    after = compute_score([facts("done"), facts("let_go")])["ratio"]
    assert after > before


def test_an_empty_workspace_scores_zero_without_dividing_by_zero() -> None:
    assert compute_score([])["ratio"] == 0.0


def test_categories_show_intent_against_action() -> None:
    result = by_category(
        [facts("done", intent="cook"), facts(intent="fitness"), facts(intent="fitness")]
    )
    assert {r["category"]: (r["saved"], r["acted"]) for r in result} == {
        "fitness": (2, 0),
        "cook": (1, 1),
    }


@pytest.mark.parametrize(
    ("offsets", "expected"),
    [
        ([], 0),
        ([0], 1),
        ([1], 1),  # Not done yet today doesn't break a streak.
        ([0, 1, 2], 3),
        ([0, 2], 1),
        ([2, 3], 0),
    ],
)
def test_streaks(offsets: list[int], expected: int) -> None:
    today = date(2026, 11, 7)
    assert compute_streak({today - timedelta(days=o) for o in offsets}, today) == expected


@pytest.fixture
async def workspace(client: AsyncClient, postgres: Any) -> tuple[str, dict[str, str]]:
    headers = auth_header(create_user(postgres))
    me = (await client.get("/api/v1/me", headers=headers)).json()
    return me["workspaces"][0]["id"], headers


async def ready_save(client: AsyncClient, settings: Settings, workspace: Any) -> dict[str, Any]:
    save_id = await create_note(client, workspace)
    await drain_jobs(settings)
    response = await client.get(f"/api/v1/saves/{save_id}", headers=workspace[1])
    return dict(response.json())


async def test_ingestion_suggests_a_small_first_step(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    card = await ready_save(client, settings, workspace)
    micro = [t for t in card["tasks"] if t["type"] == "micro_action"]
    assert [t["title"] for t in micro] == ["Read one problem statement"]
    assert micro[0]["status"] == "suggested"
    assert micro[0]["scheduled_for"]
    assert card["intent"] == "learn"
    assert [t["name"] for t in card["topics"]] == ["Algorithms"]


async def test_nothing_reaches_tasks_until_accepted(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    await ready_save(client, settings, workspace)
    accepted = await client.get(
        f"/api/v1/workspaces/{workspace[0]}/tasks?status=accepted", headers=workspace[1]
    )
    assert accepted.json() == []


async def test_the_full_loop_moves_the_score(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    workspace_id, headers = workspace
    card = await ready_save(client, settings, workspace)
    micro = next(t for t in card["tasks"] if t["type"] == "micro_action")

    home = (await client.get(f"/api/v1/workspaces/{workspace_id}/home", headers=headers)).json()
    assert home["score"] == {"acted": 0, "total": 1, "ratio": 0.0}
    assert micro["id"] in [t["id"] for t in home["suggested"]]

    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    accepted = await client.patch(
        f"/api/v1/tasks/{micro['id']}",
        headers=headers,
        json={"status": "accepted", "scheduled_for": past},
    )
    assert accepted.json()["status"] == "accepted"

    home = (await client.get(f"/api/v1/workspaces/{workspace_id}/home", headers=headers)).json()
    assert micro["id"] in [t["id"] for t in home["followups"]]

    done = await client.post(
        f"/api/v1/tasks/{micro['id']}/respond", headers=headers, json={"answer": "done"}
    )
    assert done.json()["task"]["status"] == "done"
    assert done.json()["next_step"]["title"] == "Solve one graph problem"

    metrics = (
        await client.get(
            f"/api/v1/workspaces/{workspace_id}/metrics/save-to-action", headers=headers
        )
    ).json()
    assert metrics["score"] == {"acted": 1, "total": 1, "ratio": 1.0}
    assert metrics["streak_days"] == 1
    assert metrics["categories"] == [{"category": "learn", "saved": 1, "acted": 1}]
    assert metrics["changed"][0]["title"] == "Read one problem statement"


async def test_not_yet_reschedules_and_counts_the_skip(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    card = await ready_save(client, settings, workspace)
    task = card["tasks"][0]
    response = await client.post(
        f"/api/v1/tasks/{task['id']}/respond", headers=workspace[1], json={"answer": "not_yet"}
    )
    updated = response.json()["task"]
    assert updated["status"] == "accepted"
    assert updated["followup_at"] > datetime.now(UTC).isoformat()


async def test_let_go_leaves_the_score_total(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    workspace_id, headers = workspace
    card = await ready_save(client, settings, workspace)
    for task in card["tasks"]:
        await client.post(
            f"/api/v1/tasks/{task['id']}/respond", headers=headers, json={"answer": "let_go"}
        )
    home = (await client.get(f"/api/v1/workspaces/{workspace_id}/home", headers=headers)).json()
    assert home["score"]["total"] == 0


async def test_followups_only_nudge_the_assignee(client: AsyncClient, postgres: Any) -> None:
    owner, teammate = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {teammate: "member"})
    past = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    await client.post(
        f"/api/v1/workspaces/{team}/tasks",
        headers=auth_header(owner),
        json={"title": "Owner's job", "scheduled_for": past},
    )
    theirs = await client.get(f"/api/v1/workspaces/{team}/home", headers=auth_header(teammate))
    assert theirs.json()["followups"] == []
    mine = await client.get(f"/api/v1/workspaces/{team}/home", headers=auth_header(owner))
    assert len(mine.json()["followups"]) == 1


async def test_viewers_cannot_touch_tasks(client: AsyncClient, postgres: Any) -> None:
    owner, viewer = create_user(postgres), create_user(postgres)
    team = create_team(postgres, owner, {viewer: "viewer"})
    created = await client.post(
        f"/api/v1/workspaces/{team}/tasks", headers=auth_header(owner), json={"title": "A job"}
    )
    task_id = created.json()["id"]
    headers = auth_header(viewer)
    edit = await client.patch(f"/api/v1/tasks/{task_id}", headers=headers, json={"title": "x"})
    assert edit.status_code == 403
    respond = await client.post(
        f"/api/v1/tasks/{task_id}/respond", headers=headers, json={"answer": "done"}
    )
    assert respond.status_code == 403
    assert (await client.delete(f"/api/v1/tasks/{task_id}", headers=headers)).status_code == 403


async def test_library_filters_and_search(
    client: AsyncClient, settings: Settings, workspace: Any
) -> None:
    workspace_id, headers = workspace
    card = await ready_save(client, settings, workspace)
    url = f"/api/v1/workspaces/{workspace_id}/saves"
    for params, count in [
        ({"mode": "study"}, 1),
        ({"mode": "work"}, 0),
        ({"source_type": "text"}, 1),
        ({"q": "cycles"}, 1),
        ({"q": "graphs explained"}, 1),
        ({"q": "zzzznothing"}, 0),
        ({"status": "ready"}, 1),
        ({"topic": card["topics"][0]["id"]}, 1),
    ]:
        response = await client.get(url, headers=headers, params=params)
        assert response.status_code == 200, params
        assert len(response.json()["items"]) == count, params


async def test_search_is_scoped_to_the_workspace(
    client: AsyncClient, settings: Settings, workspace: Any, postgres: Any
) -> None:
    await ready_save(client, settings, workspace)
    other = auth_header(create_user(postgres))
    me = (await client.get("/api/v1/me", headers=other)).json()
    response = await client.get(
        f"/api/v1/workspaces/{me['workspaces'][0]['id']}/saves",
        headers=other,
        params={"q": "cycles"},
    )
    assert response.json()["items"] == []


async def test_hybrid_retrieval_finds_chunks_under_rls(
    client: AsyncClient, settings: Settings, workspace: Any, app: Any, postgres: Any
) -> None:
    await ready_save(client, settings, workspace)
    query = "detecting cycles"
    embedding = (await FakeEmbeddings().embed([query]))[0]
    owner = (await client.get("/api/v1/me", headers=workspace[1])).json()["user"]["id"]
    filters = SearchFilters(UUID(workspace[0]))
    async with user_session(CurrentUser(UUID(owner), None)) as session:
        found = await hybrid_search(session, query, embedding, filters)
    assert found and "cycles" in found[0].text

    stranger = create_user(postgres)
    async with user_session(CurrentUser(stranger, None)) as session:
        assert await hybrid_search(session, query, embedding, filters) == []
