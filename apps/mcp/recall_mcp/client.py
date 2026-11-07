"""A small client for the Recall API. The API enforces all permissions."""

from typing import Any

import httpx


class RecallApiError(Exception):
    pass


class RecallClient:
    def __init__(self, base_url: str, api_key: str, http: httpx.AsyncClient | None = None) -> None:
        self._base = f"{base_url.rstrip('/')}/api/v1"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._http = http or httpx.AsyncClient(timeout=60)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(
                method, f"{self._base}{path}", headers=self._headers, **kwargs
            )
        except httpx.HTTPError as error:
            raise RecallApiError("Could not reach Recall") from error
        if response.status_code == 401:
            raise RecallApiError("Your Recall API key was refused")
        if response.status_code >= 400:
            detail = response.json().get("detail", "") if response.content else ""
            raise RecallApiError(f"Recall returned {response.status_code}: {detail}")
        return response.json() if response.content else None

    async def default_workspace(self, name: str | None = None) -> str:
        me = await self._request("GET", "/me")
        workspaces = me["workspaces"]
        if not workspaces:
            raise RecallApiError("This account has no workspaces")
        if name:
            for workspace in workspaces:
                if workspace["name"].lower() == name.lower():
                    return str(workspace["id"])
            raise RecallApiError(f"No workspace named {name!r}")
        return str(workspaces[0]["id"])

    async def search_saves(
        self, query: str, workspace: str | None, limit: int
    ) -> list[dict[str, Any]]:
        workspace_id = await self.default_workspace(workspace)
        result = await self._request(
            "GET", f"/workspaces/{workspace_id}/saves", params={"q": query, "limit": limit}
        )
        return [
            {
                "id": item["id"],
                "title": item["title"],
                "summary": item["summary"],
                "url": item["source_url"],
                "status": item["status"],
            }
            for item in result["items"]
        ]

    async def get_save(self, save_id: str) -> dict[str, Any]:
        save = await self._request("GET", f"/saves/{save_id}")
        return {
            key: save[key]
            for key in ("id", "title", "summary", "key_points", "source_url", "status", "resources")
        }

    async def list_tasks(self, status: str | None, workspace: str | None) -> list[dict[str, Any]]:
        workspace_id = await self.default_workspace(workspace)
        params = {"status": status} if status else {}
        tasks = await self._request("GET", f"/workspaces/{workspace_id}/tasks", params=params)
        return [
            {key: task[key] for key in ("id", "title", "status", "scheduled_for", "due_at")}
            for task in tasks
        ]

    async def create_save(
        self, url: str | None, text: str | None, workspace: str | None
    ) -> dict[str, Any]:
        workspace_id = await self.default_workspace(workspace)
        save = await self._request(
            "POST", f"/workspaces/{workspace_id}/saves", json={"url": url, "text": text}
        )
        return {"id": save["id"], "status": save["status"]}
