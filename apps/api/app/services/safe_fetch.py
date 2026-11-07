"""Fetches user-supplied URLs without letting them reach internal systems (SSRF).

Every hop of a redirect chain is checked, because a public URL can redirect to, say,
a cloud metadata address. Responses are size-capped while streaming.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 5
TIMEOUT = httpx.Timeout(20, connect=8)
USER_AGENT = "RecallBot/1.0 (+content capture on behalf of a user)"


class BlockedUrlError(ValueError):
    """The URL points somewhere we refuse to fetch."""


class FetchError(Exception):
    """The URL couldn't be fetched."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    content: bytes
    content_type: str


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise BlockedUrlError("Only http and https links can be saved")
    if not parts.hostname or parts.username or parts.password:
        raise BlockedUrlError("That link isn't valid")
    if parts.port not in {None, 80, 443}:
        raise BlockedUrlError("That link uses an unsupported port")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            parts.hostname, parts.port or 443, type=socket.SOCK_STREAM
        )
    except socket.gaierror as error:
        raise FetchError("That site couldn't be found") from error
    if not infos or not all(is_public_address(str(info[4][0])) for info in infos):
        raise BlockedUrlError("That link points to a private address")


async def safe_fetch(
    url: str, *, max_bytes: int, client: httpx.AsyncClient | None = None
) -> FetchedPage:
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False)
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await assert_public_url(current)
            async with http.stream("GET", current, headers={"User-Agent": USER_AGENT}) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("That link redirected nowhere")
                    current = urljoin(current, location)
                    continue
                if response.status_code >= 400:
                    raise FetchError(f"That site returned an error ({response.status_code})")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise FetchError("That file is too large")
                return FetchedPage(
                    url=current,
                    content=bytes(body),
                    content_type=response.headers.get("content-type", "").split(";")[0].strip(),
                )
        raise FetchError("That link redirected too many times")
    except httpx.HTTPError as error:
        raise FetchError("That site couldn't be reached") from error
    finally:
        if owns_client:
            await http.aclose()
