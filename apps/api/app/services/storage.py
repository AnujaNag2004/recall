"""Uploaded files live in a private Supabase Storage bucket."""

from functools import lru_cache
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.config import Settings, get_settings

TIMEOUT = httpx.Timeout(120, connect=10)


class StorageError(Exception):
    pass


class FileStore(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...
    async def download(self, path: str) -> bytes: ...
    async def signed_url(self, path: str, expires_in: int = 3600) -> str: ...
    async def delete(self, path: str) -> None: ...


class SupabaseStorage:
    def __init__(self, settings: Settings) -> None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise StorageError("Supabase Storage isn't configured")
        self._base = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self._bucket = settings.supabase_storage_bucket
        key = settings.supabase_service_role_key
        self._headers = {"Authorization": f"Bearer {key}", "apikey": key}

    def _object(self, path: str) -> str:
        return f"{self._base}/object/{self._bucket}/{quote(path)}"

    async def _request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.request(method, url, **kwargs)  # type: ignore[arg-type]
        except httpx.HTTPError as error:
            raise StorageError("Could not reach storage") from error
        if response.status_code >= 400:
            raise StorageError(f"Storage returned HTTP {response.status_code}")
        return response

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        headers = {**self._headers, "Content-Type": content_type}
        await self._request("POST", self._object(path), headers=headers, content=data)

    async def download(self, path: str) -> bytes:
        return (await self._request("GET", self._object(path), headers=self._headers)).content

    async def signed_url(self, path: str, expires_in: int = 3600) -> str:
        url = f"{self._base}/object/sign/{self._bucket}/{quote(path)}"
        response = await self._request(
            "POST", url, headers=self._headers, json={"expiresIn": expires_in}
        )
        return f"{self._base}{response.json()['signedURL']}"

    async def delete(self, path: str) -> None:
        await self._request("DELETE", self._object(path), headers=self._headers)


@lru_cache
def get_file_store() -> FileStore:
    return SupabaseStorage(get_settings())
