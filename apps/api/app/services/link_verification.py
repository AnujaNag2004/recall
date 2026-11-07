"""Turns a mentioned name into a verified official link.

The rule that matters: **the model never supplies a URL.** It chooses an index into
real search results, and `pick_candidate` rejects anything outside that list. Every
candidate then has to pass mechanical checks before it can be called verified.
"""

import html
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import BaseModel, Field

from app.providers.base import LLMProvider, SearchProvider, SearchResult
from app.providers.structured import complete_structured
from app.services.safe_fetch import BlockedUrlError, FetchedPage, FetchError, safe_fetch

VERIFIED_THRESHOLD = 0.7
PAGE_MAX_BYTES = 2 * 1024 * 1024

# Places that talk about a thing without being the thing's official site.
BLOCKLIST = {
    "bit.ly", "t.co", "tinyurl.com", "linktr.ee",
    "pinterest.com", "quora.com", "medium.com", "reddit.com",
    "facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com",
    "g2.com", "capterra.com", "producthunt.com", "alternativeto.net",
}  # fmt: skip
# Legitimately official for the entity types that live there.
OFFICIAL_HOSTS = {"repo": {"github.com", "gitlab.com"}, "person": {"linkedin.com", "github.com"}}
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_DESCRIPTION_RE = re.compile(
    r"<meta[^>]+(?:name|property)=[\"'](?:og:)?description[\"'][^>]+content=[\"']([^\"']*)",
    re.IGNORECASE,
)
_STOPWORDS = {"the", "a", "an", "of", "and", "for", "to", "in", "on", "by"}


class CandidateChoice(BaseModel):
    index: int | None = Field(
        description="Number of the official result for this entity, or null if none is"
    )


@dataclass(frozen=True)
class VerifiedResource:
    url: str
    domain: str
    title: str | None
    description: str | None
    favicon_url: str
    pricing: str
    category: str
    confidence: float
    verified: bool


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def is_blocklisted(domain: str) -> bool:
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKLIST)


def name_tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def brand_matches_domain(name: str, domain: str) -> bool:
    """Whole labels only, so a lookalike such as notstripe-reviews.example can't pass."""
    tokens = name_tokens(name)
    if not tokens:
        return False
    labels = domain.split(".")[:-1]
    segments = {segment for label in labels for segment in label.split("-")}
    joined = "".join(tokens)
    return (
        joined in labels
        or joined in segments
        or any(len(token) >= 4 and token in segments for token in tokens)
    )


def pick_candidate(index: int | None, results: list[SearchResult]) -> SearchResult | None:
    """The only way a URL enters the Resource Panel. Out-of-range answers are refused."""
    if index is None or isinstance(index, bool) or not 0 <= index < len(results):
        return None
    return results[index]


def assert_url_from_results(url: str, results: list[SearchResult]) -> None:
    """A last check before storing: every stored URL must be one search returned."""
    if url not in {result.url for result in results}:
        raise ValueError("Refusing a URL that isn't in the search results")


def guess_pricing(page_text: str, entity_type: str) -> str:
    text = page_text.lower()
    if entity_type == "book":
        return "paid"
    has_free = bool(re.search(r"\b(free|open[- ]source)\b", text))
    has_paid = bool(re.search(r"\b(pricing|per month|/mo|subscribe|buy now|upgrade)\b", text))
    if has_free and has_paid:
        return "freemium"
    if has_free:
        return "free"
    return "paid" if has_paid else "unknown"


def score_candidate(
    *, name: str, entity_type: str, result: SearchResult, page_title: str | None, reachable: bool
) -> float:
    """Mechanical signals only, so a model can't talk its way to a high score."""
    if not reachable:
        return min(0.3, result.score * 0.3)
    domain = domain_of(result.url)
    official_host = domain in OFFICIAL_HOSTS.get(entity_type, set())
    tokens = name_tokens(name)
    title = (page_title or "").lower()
    score = 0.2 + 0.15 * min(max(result.score, 0.0), 1.0)
    if brand_matches_domain(name, domain):
        score += 0.4
    if official_host and tokens and all(t in result.url.lower() for t in tokens):
        score += 0.4
    if tokens and all(token in title for token in tokens):
        score += 0.25
    if urlsplit(result.url).scheme == "https":
        score += 0.05
    return round(min(score, 1.0), 2)


def parse_page(page: FetchedPage) -> tuple[str | None, str | None, str]:
    body = page.content[: 512 * 1024].decode("utf-8", errors="ignore")
    title = _TITLE_RE.search(body)
    description = _DESCRIPTION_RE.search(body)
    return (
        html.unescape(title.group(1)).strip()[:200] if title else None,
        html.unescape(description.group(1)).strip()[:300] if description else None,
        body,
    )


async def _fetch_page(url: str) -> FetchedPage | None:
    try:
        return await safe_fetch(url, max_bytes=PAGE_MAX_BYTES)
    except (FetchError, BlockedUrlError):
        return None


async def resolve_entity(
    *,
    name: str,
    entity_type: str,
    context: str,
    search: SearchProvider,
    llm: LLMProvider,
    system: str,
    fetch_page: Callable[[str], Awaitable[FetchedPage | None]] = _fetch_page,
) -> VerifiedResource | None:
    """Search, let the model choose among real results, then check the choice."""
    results = await search.search(f"{name} official site {entity_type}", max_results=5)
    results = [
        r
        for r in results
        if urlsplit(r.url).scheme in {"http", "https"}
        and (
            not is_blocklisted(domain_of(r.url))
            or domain_of(r.url) in OFFICIAL_HOSTS.get(entity_type, set())
        )
    ]
    if not results:
        return None

    listing = "\n".join(
        f"{i}. {r.title} ({domain_of(r.url)}): {r.snippet[:160]}" for i, r in enumerate(results)
    )
    choice = await complete_structured(
        llm,
        f"Which search result is the official page for the {entity_type} named {name!r}? "
        f"It was mentioned like this: {context[:200]!r}\n\nResults:\n{listing}\n\n"
        "Answer with its number. Answer null if none is clearly official.",
        CandidateChoice,
        system=system,
    )
    candidate = pick_candidate(choice.index, results)
    if candidate is None:
        return None
    assert_url_from_results(candidate.url, results)

    page = await fetch_page(candidate.url)
    title, description, body = parse_page(page) if page else (None, None, "")
    confidence = score_candidate(
        name=name,
        entity_type=entity_type,
        result=candidate,
        page_title=title,
        reachable=page is not None,
    )
    domain = domain_of(candidate.url)
    return VerifiedResource(
        url=candidate.url,
        domain=domain,
        title=title or candidate.title or None,
        description=description or candidate.snippet[:200] or None,
        favicon_url=f"https://{domain}/favicon.ico",
        pricing=guess_pricing(f"{body[:20000]} {candidate.snippet}", entity_type),
        category=entity_type,
        confidence=confidence,
        verified=confidence >= VERIFIED_THRESHOLD,
    )
