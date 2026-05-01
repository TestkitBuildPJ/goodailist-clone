"""Ingestor — orchestrates one cron tick.

Read watchlist from ``repos`` table → call :class:`GithubClient` → write
:class:`RepoStarSnapshot` + update :class:`Repo` aggregates → log one
:class:`IngestRun` audit row.

Pure async; no FastAPI dependency.  The scheduler module wires this into
the application lifespan.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_engine
from app.ingest.etag_store import EtagStore
from app.ingest.github_client import GithubClient, RateLimitError, UpstreamError
from app.models import IngestRun, Repo, RepoStarSnapshot

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    """Result of one ingestor run, mirrored into the ``ingest_runs`` row."""

    run_id: int | None = None
    repos_updated: int = 0
    api_calls: int = 0
    etag_hits: int = 0
    status: str = "running"
    error_msg: str | None = None
    failed_repos: list[str] = field(default_factory=list)


def _now() -> datetime:
    """Return current UTC wall-clock as a naive datetime (DB stores naive)."""
    return datetime.now(tz=UTC).replace(tzinfo=None)


def _begin_run(maker: sessionmaker[Session]) -> int:
    with maker() as session:
        run = IngestRun(started_at=_now(), status="running")
        session.add(run)
        session.commit()
        return int(run.id)


def _finalize_run(
    maker: sessionmaker[Session],
    stats: RunStats,
) -> None:
    if stats.run_id is None:
        return
    with maker() as session:
        run = session.get(IngestRun, stats.run_id)
        if run is None:
            return
        run.finished_at = _now()
        run.status = stats.status
        run.repos_updated = stats.repos_updated
        run.api_calls = stats.api_calls
        run.etag_hits = stats.etag_hits
        run.error_msg = stats.error_msg
        session.commit()


def _watchlist(maker: sessionmaker[Session]) -> list[tuple[int, str, str]]:
    with maker() as session:
        rows = session.query(Repo).order_by(Repo.id).all()
        return [(int(r.id), str(r.org), str(r.name)) for r in rows]


async def run_once(
    *,
    client: GithubClient | None = None,
    store: EtagStore | None = None,
    engine: Engine | None = None,
    sessionmaker_factory: sessionmaker[Session] | None = None,
) -> RunStats:
    """Execute one ingest cycle.  Returns aggregated stats.

    ``client`` and ``sessionmaker_factory`` are injected so tests can
    swap them; production calls leave them ``None`` and we build defaults.
    """
    if sessionmaker_factory is None:
        eng: Engine = engine if engine is not None else get_engine()
        sessionmaker_factory = sessionmaker(
            bind=eng, autoflush=False, expire_on_commit=False, future=True
        )

    stats = RunStats()
    stats.run_id = _begin_run(sessionmaker_factory)

    owns_client = client is None
    gh = client or GithubClient(store=store)

    rate_limited = False
    try:
        watch = _watchlist(sessionmaker_factory)
        for repo_id, owner, name in watch:
            try:
                fetch = await gh.fetch_repo(owner, name)
            except RateLimitError as exc:
                # Token-scoped rate limit — every subsequent call would also 429.
                # Stop iterating and finalize whatever we already have.
                logger.warning("ingest aborting after rate-limit on %s/%s: %s", owner, name, exc)
                stats.failed_repos.append(f"{owner}/{name}")
                rate_limited = True
                break
            except UpstreamError as exc:
                logger.warning("ingest skip %s/%s: %s", owner, name, exc)
                stats.failed_repos.append(f"{owner}/{name}")
                continue

            captured_at = _now()
            with sessionmaker_factory() as session:
                repo = session.get(Repo, repo_id)
                if repo is None:
                    continue
                if fetch.cached:
                    # 304 — stars unchanged on GitHub side.  Advance
                    # ``stars_1d_ago`` to the current value so the table delta
                    # reflects "no change in last 24h" instead of staying
                    # frozen on the previous non-304 day.
                    snapshot_stars = int(repo.stars)
                    snapshot_forks = int(repo.forks)
                    repo.stars_1d_ago = int(repo.stars)
                else:
                    assert fetch.stars is not None and fetch.forks is not None
                    # Advance 7d-ago from snapshots ≥ 7 days old (best-effort).
                    seven_d = (
                        session.query(RepoStarSnapshot)
                        .filter(
                            RepoStarSnapshot.repo_id == repo_id,
                            RepoStarSnapshot.captured_at <= captured_at - timedelta(days=7),
                        )
                        .order_by(RepoStarSnapshot.captured_at.desc())
                        .first()
                    )
                    if seven_d is not None:
                        repo.stars_7d_ago = int(seven_d.stars)
                    repo.stars_1d_ago = int(repo.stars)
                    repo.stars = int(fetch.stars)
                    repo.forks = int(fetch.forks)
                    snapshot_stars = int(fetch.stars)
                    snapshot_forks = int(fetch.forks)

                session.add(
                    RepoStarSnapshot(
                        repo_id=repo_id,
                        captured_at=captured_at,
                        stars=snapshot_stars,
                        forks=snapshot_forks,
                    )
                )
                session.commit()
            stats.repos_updated += 1

        stats.api_calls = gh.api_calls
        stats.etag_hits = gh.etag_hits

        if rate_limited:
            stats.status = "partial" if stats.repos_updated > 0 else "failed"
            stats.error_msg = (
                f"rate-limited after {stats.repos_updated}; failed: "
                f"{', '.join(stats.failed_repos[:5])}"
            )
        elif stats.failed_repos:
            stats.status = "partial"
            stats.error_msg = f"failed: {', '.join(stats.failed_repos[:5])}"
        else:
            stats.status = "success"

    except Exception as exc:  # noqa: BLE001 — top-level boundary, log and finalize
        logger.exception("ingest run %s crashed", stats.run_id)
        stats.status = "failed"
        stats.error_msg = f"{type(exc).__name__}: {exc}"[:500]
        stats.api_calls = gh.api_calls
        stats.etag_hits = gh.etag_hits
    finally:
        if owns_client:
            with suppress(Exception):
                await gh.aclose()
        _finalize_run(sessionmaker_factory, stats)

    return stats
