"""The no-hallucinated-links guarantee, and the checks behind 'verified'."""

import json
from typing import Any

import pytest

from app.providers.base import SearchResult
from app.services.link_verification import (
    assert_url_from_results,
    brand_matches_domain,
    guess_pricing,
    is_blocklisted,
    pick_candidate,
    resolve_entity,
    score_candidate,
)
from app.services.safe_fetch import FetchedPage
from tests.fakes import FakeLLM, FakeSearch

RESULTS = [
    SearchResult("VisuAlgo", "https://visualgo.net/en", "Visualising algorithms", 0.9),
    SearchResult("Top tools", "https://www.g2.com/visualgo", "Reviews", 0.8),
    SearchResult("Blog", "https://someblog.example/visualgo-review", "A review", 0.5),
]


def test_candidates_can_only_come_from_the_results() -> None:
    assert pick_candidate(0, RESULTS) is RESULTS[0]
    for bad in [None, -1, 3, 99]:
        assert pick_candidate(bad, RESULTS) is None


def test_a_url_outside_the_search_results_is_rejected() -> None:
    assert_url_from_results("https://visualgo.net/en", RESULTS)
    with pytest.raises(ValueError, match="isn't in the search results"):
        assert_url_from_results("https://invented-by-a-model.example", RESULTS)


async def fake_page(url: str) -> FetchedPage:
    html = b"<html><head><title>VisuAlgo - visualising</title></head>free to use</html>"
    return FetchedPage(url, html, "text/html")


async def no_page(url: str) -> None:
    return None


async def resolve(llm_answer: Any, fetch_page: Any = fake_page) -> Any:
    return await resolve_entity(
        name="VisuAlgo",
        entity_type="website",
        context="step through BFS on VisuAlgo",
        search=FakeSearch({"VisuAlgo": RESULTS}),
        llm=FakeLLM({"official page": json.dumps(llm_answer)}),
        system="",
        fetch_page=fetch_page,
    )


async def test_a_model_cannot_introduce_its_own_url() -> None:
    """Even a model answering with a URL gets nothing: the schema only takes an index."""
    assert await resolve({"index": 99, "url": "https://evil.example"}) is None


async def test_a_model_can_decline_to_choose() -> None:
    assert await resolve({"index": None}) is None


async def test_official_reachable_site_is_verified() -> None:
    resource = await resolve({"index": 0})
    assert resource.url == "https://visualgo.net/en"
    assert resource.verified
    assert resource.confidence >= 0.7
    assert resource.pricing == "free"
    assert resource.title == "VisuAlgo - visualising"


async def test_review_sites_never_make_the_candidate_list() -> None:
    search = FakeSearch({"VisuAlgo": RESULTS})
    llm = FakeLLM({"official page": '{"index": 1}'})
    resource = await resolve_entity(
        name="VisuAlgo",
        entity_type="website",
        context="",
        search=search,
        llm=llm,
        system="",
        fetch_page=fake_page,
    )
    # Index 1 now means the blog, because g2.com was filtered before the model saw the list.
    assert resource is not None
    assert "g2.com" not in resource.url
    assert not any("g2.com" in prompt for prompt in llm.prompts)


async def test_an_unrelated_domain_stays_unverified() -> None:
    async def unrelated_page(url: str) -> FetchedPage:
        return FetchedPage(url, b"<title>Ten tools we like</title>", "text/html")

    resource = await resolve({"index": 1}, fetch_page=unrelated_page)
    assert "someblog" in resource.url
    assert not resource.verified


async def test_a_lookalike_domain_with_a_matching_title_stays_unverified() -> None:
    result = SearchResult("Stripe", "https://notstripe-reviews.example/", "", 1.0)
    score = score_candidate(
        name="Stripe", entity_type="tool", result=result, page_title="Stripe", reachable=True
    )
    assert score < 0.7


async def test_an_unreachable_page_is_never_verified() -> None:
    resource = await resolve({"index": 0}, fetch_page=no_page)
    assert not resource.verified
    assert resource.confidence <= 0.3


def test_score_needs_a_reachable_page() -> None:
    kwargs: dict[str, Any] = {
        "name": "VisuAlgo",
        "entity_type": "website",
        "result": RESULTS[0],
        "page_title": "VisuAlgo",
    }
    assert score_candidate(reachable=True, **kwargs) > score_candidate(reachable=False, **kwargs)


@pytest.mark.parametrize(
    ("name", "domain", "expected"),
    [
        ("VisuAlgo", "visualgo.net", True),
        ("Notion AI", "notion.so", True),
        ("Introduction to Algorithms", "mitpress.mit.edu", False),
        ("Stripe", "notstripe-reviews.example", False),
        ("Stripe", "stripe.com", True),
        ("LeetCode", "leetcode.com", True),
        ("GitHub Copilot", "github.com", True),
        ("Go", "example.com", False),
    ],
)
def test_brand_matching(name: str, domain: str, expected: bool) -> None:
    assert brand_matches_domain(name, domain) is expected


def test_blocklist_covers_subdomains() -> None:
    assert is_blocklisted("old.reddit.com")
    assert not is_blocklisted("reddit-tools.example")


@pytest.mark.parametrize(
    ("text", "kind", "expected"),
    [
        ("Totally free and open source", "tool", "free"),
        ("Start free, see pricing", "tool", "freemium"),
        ("$20 per month", "tool", "paid"),
        ("nothing here", "tool", "unknown"),
        ("free chapter inside", "book", "paid"),
    ],
)
def test_pricing_guess(text: str, kind: str, expected: str) -> None:
    assert guess_pricing(text, kind) == expected
