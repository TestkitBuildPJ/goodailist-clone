"""Unit tests for :class:`app.ingest.github_client.GithubClient`.

All HTTP is mocked via ``respx``; no real network is allowed.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from app.ingest.etag_store import EtagStore
from app.ingest.github_client import (
    GITHUB_API,
    GithubClient,
    RateLimitError,
    UpstreamError,
)


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_200_returns_stars_and_forks() -> None:
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(
            200,
            json={"stargazers_count": 12345, "forks_count": 67},
            headers={"ETag": '"abc"'},
        )
    )
    async with GithubClient(token=None) as client:
        result = await client.fetch_repo("acme", "widget")
    assert result.cached is False
    assert result.stars == 12345
    assert result.forks == 67
    assert result.etag == '"abc"'
    assert client.api_calls == 1
    assert client.etag_hits == 0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_304_marks_cached_and_increments_hits() -> None:
    store = EtagStore()
    store.set("acme", "widget", '"abc"')
    route = respx.get(f"{GITHUB_API}/repos/acme/widget").mock(return_value=httpx.Response(304))
    async with GithubClient(token=None, store=store) as client:
        result = await client.fetch_repo("acme", "widget")
    sent = route.calls[0].request
    assert sent.headers.get("if-none-match") == '"abc"'
    assert result.cached is True
    assert result.stars is None
    assert result.forks is None
    assert client.etag_hits == 1
    assert client.api_calls == 1


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_stores_etag_on_first_200() -> None:
    store = EtagStore()
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(
            200,
            json={"stargazers_count": 1, "forks_count": 0},
            headers={"ETag": '"e1"'},
        )
    )
    async with GithubClient(token=None, store=store) as client:
        await client.fetch_repo("acme", "widget")
    assert store.get("acme", "widget") == '"e1"'


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_429_then_200_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.ingest.github_client.asyncio.sleep", fake_sleep)

    reset_in = int(time.time()) + 5
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"X-RateLimit-Reset": str(reset_in)},
                json={"message": "rate limited"},
            ),
            httpx.Response(
                200,
                json={"stargazers_count": 3, "forks_count": 1},
                headers={"ETag": '"e2"'},
            ),
        ]
    )
    async with GithubClient(token=None) as client:
        result = await client.fetch_repo("acme", "widget")
    assert result.stars == 3
    assert client.api_calls == 2
    assert sleeps and sleeps[0] >= 0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_429_twice_raises_rate_limit_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("app.ingest.github_client.asyncio.sleep", fake_sleep)

    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(429, headers={"X-RateLimit-Reset": "0"})
    )
    async with GithubClient(token=None) as client:
        with pytest.raises(RateLimitError):
            await client.fetch_repo("acme", "widget")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_5xx_raises_upstream_error() -> None:
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(503, json={"message": "boom"})
    )
    async with GithubClient(token=None) as client:
        with pytest.raises(UpstreamError):
            await client.fetch_repo("acme", "widget")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_malformed_json_raises_upstream_error() -> None:
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(200, content=b"not-json{", headers={"ETag": '"e"'})
    )
    async with GithubClient(token=None) as client:
        with pytest.raises(UpstreamError):
            await client.fetch_repo("acme", "widget")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_repo_missing_fields_raises_upstream_error() -> None:
    respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(200, json={"name": "widget"})
    )
    async with GithubClient(token=None) as client:
        with pytest.raises(UpstreamError):
            await client.fetch_repo("acme", "widget")


@pytest.mark.asyncio
@respx.mock
async def test_token_is_sent_in_authorization_header() -> None:
    route = respx.get(f"{GITHUB_API}/repos/acme/widget").mock(
        return_value=httpx.Response(200, json={"stargazers_count": 1, "forks_count": 0})
    )
    async with GithubClient(token="secret-token") as client:
        await client.fetch_repo("acme", "widget")
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer secret-token"
