"""Async GitHub REST v3 client with ETag + rate-limit handling.

Pure HTTP client — does not touch the database.  Caller owns persistence
(see ``app.ingest.ingestor`` in TIP-B03).

Behaviours:
- Sends ``If-None-Match`` when an ETag is cached.  ``304`` → ``RepoFetch.cached=True``.
- Honours GitHub's ``X-RateLimit-Reset`` header on ``429``: sleeps until reset
  then retries **once**.  A second ``429`` propagates as ``RateLimitError``.
- Logs only redacted metadata; the token is never written to logs.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.ingest.etag_store import EtagStore

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 10.0


class RateLimitError(RuntimeError):
    """Raised when GitHub returns 429 twice in a row."""


class UpstreamError(RuntimeError):
    """Raised when GitHub returns a non-handled 4xx/5xx."""


@dataclass(frozen=True)
class RepoFetch:
    """Result of one ``GET /repos/{owner}/{repo}`` call."""

    owner: str
    repo: str
    cached: bool
    """True if the response was ``304 Not Modified`` (ETag hit)."""

    stars: int | None
    forks: int | None
    etag: str | None


def _auth_header(token: str | None) -> dict[str, str]:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def _redact(headers: dict[str, str]) -> dict[str, str]:
    """Strip sensitive values before logging."""
    cleaned = dict(headers)
    if "Authorization" in cleaned:
        cleaned["Authorization"] = "<redacted>"
    return cleaned


class GithubClient:
    """Async client.  One instance per cron run; close via ``aclose``."""

    def __init__(
        self,
        token: str | None = None,
        store: EtagStore | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self._store = store if store is not None else EtagStore()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=GITHUB_API,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                **_auth_header(self._token),
            },
            timeout=timeout,
        )
        self.api_calls = 0
        self.etag_hits = 0

    @property
    def store(self) -> EtagStore:
        return self._store

    async def fetch_repo(self, owner: str, repo: str) -> RepoFetch:
        """Fetch ``/repos/{owner}/{repo}``.  Updates ``api_calls`` / ``etag_hits``."""
        return await self._fetch_repo(owner, repo, retry=True)

    async def _fetch_repo(self, owner: str, repo: str, *, retry: bool) -> RepoFetch:
        headers: dict[str, str] = {}
        cached_etag = self._store.get(owner, repo)
        if cached_etag:
            headers["If-None-Match"] = cached_etag

        self.api_calls += 1
        response = await self._client.get(f"/repos/{owner}/{repo}", headers=headers)

        if response.status_code == 304:
            self.etag_hits += 1
            return RepoFetch(
                owner=owner, repo=repo, cached=True, stars=None, forks=None, etag=cached_etag
            )

        if response.status_code == 200:
            return self._parse_ok(owner, repo, response)

        if response.status_code == 429:
            if not retry:
                raise RateLimitError(f"{owner}/{repo}: rate-limited twice")
            await self._sleep_until_reset(response)
            return await self._fetch_repo(owner, repo, retry=False)

        raise UpstreamError(f"{owner}/{repo}: unexpected {response.status_code} from GitHub")

    def _parse_ok(self, owner: str, repo: str, response: httpx.Response) -> RepoFetch:
        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise UpstreamError(f"{owner}/{repo}: malformed JSON") from exc

        stars = payload.get("stargazers_count")
        forks = payload.get("forks_count")
        etag = response.headers.get("ETag")
        if etag:
            self._store.set(owner, repo, etag)
        if not isinstance(stars, int) or not isinstance(forks, int):
            raise UpstreamError(f"{owner}/{repo}: missing stargazers_count/forks_count")
        return RepoFetch(owner=owner, repo=repo, cached=False, stars=stars, forks=forks, etag=etag)

    async def _sleep_until_reset(self, response: httpx.Response) -> None:
        reset_str = response.headers.get("X-RateLimit-Reset")
        if reset_str is None:
            sleep_s = 1.0
        else:
            try:
                reset_at = int(reset_str)
                sleep_s = max(0.0, reset_at - time.time())
            except ValueError:
                sleep_s = 1.0
        sleep_s = min(sleep_s, 60.0)  # safety cap
        logger.warning("github rate-limited; sleeping %.1fs", sleep_s)
        await asyncio.sleep(sleep_s)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> GithubClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
