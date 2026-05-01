"""Tests for ``app.freshness`` + the stale banner / footer in ``base.html``.

We exercise three scenarios for the ``Freshness`` helper (no snapshots,
fresh snapshot, stale snapshot) plus two HTML-level smoke checks that
the rendered ``/repos`` page wires the helper into the template
correctly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.freshness import STALE_THRESHOLD, Freshness, compute_freshness
from app.models import Repo, RepoStarSnapshot


def test_compute_freshness_returns_no_snapshots_marker(engine: Engine) -> None:
    """With zero snapshot rows, the helper signals "no data yet"."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        f = compute_freshness(s)
    assert isinstance(f, Freshness)
    assert f.has_snapshots is False
    assert f.is_stale is False
    assert f.last_captured_at is None
    assert f.age is None
    assert f.hours_ago is None


def test_compute_freshness_fresh_snapshot_is_not_stale(engine: Engine) -> None:
    """A snapshot 2h old is reported as fresh (well under the 24h threshold)."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    now = datetime(2026, 5, 1, 12, 0)
    with Maker() as s:
        s.add(
            Repo(
                id=1,
                org="o",
                name="n",
                stars=1,
                stars_1d_ago=1,
                stars_7d_ago=1,
                forks=0,
                description="t",
                category="Tools",
                created_at=datetime(2024, 1, 1).date(),
                updated_at=datetime(2026, 5, 1).date(),
            )
        )
        s.add(
            RepoStarSnapshot(
                repo_id=1,
                captured_at=now - timedelta(hours=2),
                stars=1,
                forks=0,
            )
        )
        s.commit()
        f = compute_freshness(s, now=now)
    assert f.has_snapshots is True
    assert f.is_stale is False
    assert f.hours_ago is not None
    assert 1.99 < f.hours_ago < 2.01


def test_compute_freshness_marks_stale_after_24h(engine: Engine) -> None:
    """A snapshot 25h old crosses the staleness threshold."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    now = datetime(2026, 5, 1, 12, 0)
    with Maker() as s:
        s.add(
            Repo(
                id=1,
                org="o",
                name="n",
                stars=1,
                stars_1d_ago=1,
                stars_7d_ago=1,
                forks=0,
                description="t",
                category="Tools",
                created_at=datetime(2024, 1, 1).date(),
                updated_at=datetime(2026, 5, 1).date(),
            )
        )
        s.add(
            RepoStarSnapshot(
                repo_id=1,
                captured_at=now - timedelta(hours=25),
                stars=1,
                forks=0,
            )
        )
        s.commit()
        f = compute_freshness(s, now=now)
    assert f.is_stale is True
    assert f.age is not None
    assert f.age > STALE_THRESHOLD


def test_compute_freshness_default_now_uses_utc(engine: Engine) -> None:
    """Without an explicit ``now`` arg the helper uses UTC ≈ datetime.now()."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    real_now = datetime.now(tz=UTC).replace(tzinfo=None)
    with Maker() as s:
        s.add(
            Repo(
                id=1,
                org="o",
                name="n",
                stars=1,
                stars_1d_ago=1,
                stars_7d_ago=1,
                forks=0,
                description="t",
                category="Tools",
                created_at=datetime(2024, 1, 1).date(),
                updated_at=real_now.date(),
            )
        )
        s.add(
            RepoStarSnapshot(
                repo_id=1,
                captured_at=real_now - timedelta(minutes=5),
                stars=1,
                forks=0,
            )
        )
        s.commit()
        f = compute_freshness(s)
    assert f.has_snapshots is True
    assert f.is_stale is False  # 5 minutes ago is not stale


def test_repos_page_renders_footer_with_github_link(client: TestClient) -> None:
    """``/repos`` HTML must include the GitHub attribution footer."""
    body = client.get("/repos").text
    assert 'data-test="data-source-footer"' in body
    assert 'href="https://github.com/"' in body
    # Phase A seed has no snapshots → footer shows "no snapshots yet" text.
    assert "No snapshots yet" in body
    # No stale banner on a no-snapshot fresh deploy.
    assert 'data-test="stale-banner"' not in body


def test_charts_page_includes_data_source_footer(client: TestClient) -> None:
    """``/charts`` must inherit the same footer (it extends base.html)."""
    body = client.get("/charts").text
    assert 'data-test="data-source-footer"' in body
    assert "github.com" in body


def test_repos_page_shows_stale_banner_when_snapshots_old(
    engine: Engine,
) -> None:
    """When latest snapshot >24h old, the page renders the stale banner.

    We use a TestClient with a session-override so the ``/repos`` route
    sees the rows we wrote here (rather than a fresh seed).
    """
    from fastapi import FastAPI

    from app import db as db_module
    from app.main import create_app
    from app.seed import seed_into

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        # Single very old snapshot — past the 24h staleness threshold.
        s.add(
            RepoStarSnapshot(
                repo_id=1,
                captured_at=datetime(2020, 1, 1, 3, 0),
                stars=42,
                forks=0,
            )
        )
        s.commit()

    app: FastAPI = create_app()

    def _override_session() -> Generator[Session, None, None]:
        with Maker() as session:
            yield session

    app.dependency_overrides[db_module.get_session] = _override_session
    with TestClient(app) as c:
        body = c.get("/repos").text

    assert 'data-test="stale-banner"' in body
    assert "may be stale" in body


# Re-export to satisfy the type-checker for the inner generator above.
from collections.abc import Generator  # noqa: E402
