"""Tests for :func:`app.ingest.ingestor.run_once`.

The GitHub HTTP layer is fully mocked via ``respx``; an in-memory SQLite
DB is provided by the ``engine`` + ``seeded_session`` fixtures from conftest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.ingest.etag_store import EtagStore
from app.ingest.github_client import GITHUB_API, GithubClient, RateLimitError
from app.ingest.ingestor import run_once
from app.models import IngestRun, Repo, RepoStarSnapshot
from app.seed import seed_into


def _seeded_maker(engine: Engine) -> sessionmaker[object]:
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
    return Maker


def _mock_repo_200(owner: str, name: str, stars: int, forks: int = 0) -> None:
    respx.get(f"{GITHUB_API}/repos/{owner}/{name}").mock(
        return_value=httpx.Response(
            200,
            json={"stargazers_count": stars, "forks_count": forks},
            headers={"ETag": f'"{owner}-{name}"'},
        )
    )


@respx.mock
async def test_run_once_writes_snapshot_per_repo(engine: Engine) -> None:
    Maker = _seeded_maker(engine)

    with Maker() as s:
        owners = [(r.id, r.org, r.name) for r in s.query(Repo).all()]
    for _id, owner, name in owners:
        _mock_repo_200(owner, name, stars=1234, forks=5)

    stats = await run_once(sessionmaker_factory=Maker)

    assert stats.status == "success"
    assert stats.repos_updated == len(owners)
    assert stats.api_calls == len(owners)
    assert stats.etag_hits == 0
    with Maker() as s:
        snaps = s.query(RepoStarSnapshot).all()
        assert len(snaps) == len(owners)
        assert {snap.stars for snap in snaps} == {1234}


@respx.mock
async def test_run_once_records_etag_hits(engine: Engine) -> None:
    Maker = _seeded_maker(engine)
    store = EtagStore()

    with Maker() as s:
        owners = [(r.id, r.org, r.name) for r in s.query(Repo).all()][:3]

    # Pre-populate the ETag store so every fetch returns 304.
    for _id, owner, name in owners:
        store.set(owner, name, '"warm"')
        respx.get(f"{GITHUB_API}/repos/{owner}/{name}").mock(return_value=httpx.Response(304))
    # Remaining repos return 200 normally.
    with Maker() as s:
        rest = [
            (r.id, r.org, r.name) for r in s.query(Repo).all() if r.id not in {x[0] for x in owners}
        ]
    for _id, owner, name in rest:
        _mock_repo_200(owner, name, stars=10, forks=2)

    stats = await run_once(store=store, sessionmaker_factory=Maker)

    assert stats.status == "success"
    assert stats.etag_hits == 3


@respx.mock
async def test_run_once_partial_when_one_repo_fails(engine: Engine) -> None:
    Maker = _seeded_maker(engine)

    with Maker() as s:
        owners = [(r.id, r.org, r.name) for r in s.query(Repo).all()]
    bad = owners[0]
    respx.get(f"{GITHUB_API}/repos/{bad[1]}/{bad[2]}").mock(
        return_value=httpx.Response(503, json={"message": "boom"})
    )
    for _id, owner, name in owners[1:]:
        _mock_repo_200(owner, name, stars=99, forks=1)

    stats = await run_once(sessionmaker_factory=Maker)

    assert stats.status == "partial"
    assert stats.repos_updated == len(owners) - 1
    assert stats.failed_repos == [f"{bad[1]}/{bad[2]}"]
    assert stats.error_msg is not None
    with Maker() as s:
        run = s.query(IngestRun).order_by(IngestRun.id.desc()).first()
        assert run is not None
        assert run.status == "partial"


async def test_run_once_finalizes_run_even_on_total_failure(engine: Engine) -> None:
    """If the GithubClient raises mid-run, the IngestRun row is still finalized."""
    Maker = _seeded_maker(engine)

    class Boom(GithubClient):
        async def fetch_repo(self, owner: str, repo: str):  # type: ignore[no-untyped-def, override]
            raise RuntimeError("network down")

    client = Boom(token=None)
    stats = await run_once(client=client, sessionmaker_factory=Maker)

    assert stats.status == "failed"
    assert "RuntimeError" in (stats.error_msg or "")
    with Maker() as s:
        run = s.query(IngestRun).order_by(IngestRun.id.desc()).first()
        assert run is not None
        assert run.status == "failed"
        assert run.finished_at is not None


@respx.mock
async def test_run_once_updates_repo_stars_and_history(engine: Engine) -> None:
    """A successful tick should bump ``stars_1d_ago`` to the previous value."""
    Maker = _seeded_maker(engine)
    with Maker() as s:
        first = s.query(Repo).order_by(Repo.id).first()
        assert first is not None
        repo_id = int(first.id)
        before_stars = int(first.stars)
        owner, name = str(first.org), str(first.name)
        rest = [(r.id, r.org, r.name) for r in s.query(Repo).filter(Repo.id != repo_id).all()]

    _mock_repo_200(owner, name, stars=before_stars + 10, forks=99)
    for _id, o, n in rest:
        _mock_repo_200(o, n, stars=1, forks=0)

    await run_once(sessionmaker_factory=Maker)

    with Maker() as s:
        repo = s.get(Repo, repo_id)
        assert repo is not None
        assert repo.stars == before_stars + 10
        assert repo.stars_1d_ago == before_stars
        assert repo.forks == 99
        snaps = (
            s.query(RepoStarSnapshot)
            .filter_by(repo_id=repo_id)
            .order_by(RepoStarSnapshot.captured_at)
            .all()
        )
        assert len(snaps) == 1
        assert snaps[0].stars == before_stars + 10
        assert snaps[0].forks == 99


@respx.mock
async def test_run_once_advances_stars_7d_ago_from_snapshot_history(engine: Engine) -> None:
    """When a snapshot from ≥7 days ago exists, repo.stars_7d_ago should be updated."""
    Maker = _seeded_maker(engine)

    with Maker() as s:
        first = s.query(Repo).order_by(Repo.id).first()
        assert first is not None
        repo_id = int(first.id)
        owner, name = str(first.org), str(first.name)
        eight_days_ago = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=8)
        s.add(RepoStarSnapshot(repo_id=repo_id, captured_at=eight_days_ago, stars=42, forks=0))
        s.commit()
        rest = [(r.id, r.org, r.name) for r in s.query(Repo).filter(Repo.id != repo_id).all()]

    _mock_repo_200(owner, name, stars=999, forks=10)
    for _id, o, n in rest:
        _mock_repo_200(o, n, stars=1, forks=0)

    await run_once(sessionmaker_factory=Maker)

    with Maker() as s:
        repo = s.get(Repo, repo_id)
        assert repo is not None
        assert repo.stars == 999
        assert repo.stars_7d_ago == 42  # was advanced from the 8d-old snapshot


@respx.mock
async def test_run_once_aborts_on_rate_limit_but_finalizes(engine: Engine) -> None:
    """A 429 (after retry) on the *first* repo should stop iteration cleanly."""
    Maker = _seeded_maker(engine)

    with Maker() as s:
        owners = [(r.id, r.org, r.name) for r in s.query(Repo).order_by(Repo.id).all()]

    class RateLimitClient(GithubClient):
        async def fetch_repo(self, owner: str, repo: str):  # type: ignore[no-untyped-def, override]
            self.api_calls += 1
            raise RateLimitError(f"{owner}/{repo}: rate-limited twice")

    stats = await run_once(client=RateLimitClient(token=None), sessionmaker_factory=Maker)

    assert stats.status == "failed"  # nothing succeeded
    assert stats.repos_updated == 0
    assert "rate-limited" in (stats.error_msg or "")
    # The first repo was attempted, the rest were skipped.
    assert stats.failed_repos == [f"{owners[0][1]}/{owners[0][2]}"]
    with Maker() as s:
        run = s.query(IngestRun).order_by(IngestRun.id.desc()).first()
        assert run is not None
        assert run.status == "failed"


@respx.mock
async def test_run_once_advances_stars_1d_ago_on_304(engine: Engine) -> None:
    """On a 304 (cached) tick, ``stars_1d_ago`` should advance to current ``stars``.

    Regression: previously the 304 path left ``stars_1d_ago`` frozen at the
    last 200's value, so the table 1-day delta stayed permanently equal to
    the most recent positive change instead of decaying to 0 once the repo
    stopped receiving updates.
    """
    Maker = _seeded_maker(engine)
    store = EtagStore()

    with Maker() as s:
        first = s.query(Repo).order_by(Repo.id).first()
        assert first is not None
        repo_id = int(first.id)
        # simulate yesterday's 200: stars=200, stars_1d_ago was 150 (delta +50)
        first.stars = 200
        first.stars_1d_ago = 150
        s.commit()
        owner, name = str(first.org), str(first.name)
        rest = [(r.id, r.org, r.name) for r in s.query(Repo).filter(Repo.id != repo_id).all()]

    # Today: GitHub returns 304 for our repo (no change)…
    store.set(owner, name, '"warm"')
    respx.get(f"{GITHUB_API}/repos/{owner}/{name}").mock(return_value=httpx.Response(304))
    for _id, o, n in rest:
        _mock_repo_200(o, n, stars=1, forks=0)

    await run_once(store=store, sessionmaker_factory=Maker)

    with Maker() as s:
        repo = s.get(Repo, repo_id)
        assert repo is not None
        assert repo.stars == 200  # unchanged
        # advanced from 150 → 200 so today's 1d delta = 0, not +50.
        assert repo.stars_1d_ago == 200
        assert repo.stars_1d_delta == 0


# Suppress "untested" pytest collection warnings for type stubs.
_ = pytest
