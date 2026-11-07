import json

import httpx
import pytest

from recall_mcp.client import RecallApiError, RecallClient

ME = {"workspaces": [{"id": "w1", "name": "Personal"}, {"id": "w2", "name": "Squad"}]}


def client(handler) -> RecallClient:
    return RecallClient(
        "https://api.test", "rk_key", httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


async def test_search_sends_the_key_and_trims_results() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=ME)
        seen["q"] = request.url.params["q"]
        item = {
            "id": "s1",
            "title": "T",
            "summary": "S",
            "source_url": None,
            "status": "ready",
            "raw_text": "should not be returned",
        }
        return httpx.Response(200, json={"items": [item]})

    results = await client(handler).search_saves("graphs", None, 5)
    assert seen == {"auth": "Bearer rk_key", "q": "graphs"}
    assert results == [{"id": "s1", "title": "T", "summary": "S", "url": None, "status": "ready"}]


async def test_a_named_workspace_is_used() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ME)

    assert await client(handler).default_workspace("squad") == "w2"
    with pytest.raises(RecallApiError):
        await client(handler).default_workspace("nope")


async def test_a_refused_key_is_explained() -> None:
    with pytest.raises(RecallApiError, match="refused"):
        await client(lambda request: httpx.Response(401, json={})).get_save("s1")


async def test_create_save_posts_the_note() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=ME)
        assert json.loads(request.content)["text"] == "note"
        return httpx.Response(201, json={"id": "s1", "status": "pending", "title": None})

    assert await client(handler).create_save(None, "note", None) == {
        "id": "s1",
        "status": "pending",
    }
