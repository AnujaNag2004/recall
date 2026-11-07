"""Works out what kind of thing was saved, and extracts verified identifiers."""

import re
from urllib.parse import parse_qs, urlsplit

_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
_HOST_TYPES = {
    "twitter.com": "x",
    "x.com": "x",
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.watch": "facebook",
    "linkedin.com": "linkedin",
    "reddit.com": "reddit",
}
# Everything that isn't a link gets its type from the upload's content type.
UPLOAD_TYPES = {
    "application/pdf": "pdf",
    "image/png": "image",
    "image/jpeg": "image",
    "image/webp": "image",
    "audio/mpeg": "audio",
    "audio/mp4": "audio",
    "audio/x-m4a": "audio",
    "audio/wav": "audio",
    "audio/x-wav": "audio",
    "audio/webm": "audio",
    "audio/ogg": "audio",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
}


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.").removeprefix("m.")


def youtube_video_id(url: str) -> str | None:
    """Only ever returns a strict ID, so it's safe to build an embed URL from."""
    parts = urlsplit(url)
    host = _host(url)
    candidate: str | None = None
    if host == "youtu.be":
        candidate = parts.path.lstrip("/").split("/")[0]
    elif host in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        if parts.path == "/watch":
            candidate = parse_qs(parts.query).get("v", [None])[0]
        else:
            segments = parts.path.strip("/").split("/")
            if len(segments) >= 2 and segments[0] in {"shorts", "embed", "live", "v"}:
                candidate = segments[1]
    return candidate if candidate and _YOUTUBE_ID.match(candidate) else None


def detect_source_type(url: str) -> str:
    if youtube_video_id(url):
        return "youtube"
    host = _host(url)
    for domain, source_type in _HOST_TYPES.items():
        if host == domain or host.endswith(f".{domain}"):
            return source_type
    if urlsplit(url).path.lower().endswith(".pdf"):
        return "pdf"
    return "article"
