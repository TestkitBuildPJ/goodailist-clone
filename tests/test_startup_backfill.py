"""Tests for the startup-time anchor backfill (TIP-B08)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.models import Repo, RepoStarSnapshot
from app.seed import backfill_anchors_into, seed_into


def test_backfill_anchors_writes_four_per_seed_repo(engine: Engine) -> None:
    """Seed 30 repos, run backfill, assert 30×4 = 120 snapshot rows."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        inserted = backfill_anchors_into(s)
        n_snaps = s.query(RepoStarSnapshot).count()
    assert inserted == 120
    assert n_snaps == 120


def test_backfill_anchors_is_idempotent(engine: Engine) -> None:
    """Calling backfill twice should not double-insert."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        backfill_anchors_into(s)
        second = backfill_anchors_into(s)
        n_snaps = s.query(RepoStarSnapshot).count()
    assert second == 0
    assert n_snaps == 120


def test_backfill_anchors_collapses_when_dates_collide(engine: Engine) -> None:
    """Brand-new repo (created_at == updated_at) collapses to ≤ 3 rows.

    Mirrors the migration's same-day collision path: the surviving
    "current" anchor must keep the real forks count, not 0.
    """
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    same_day = date(2026, 4, 30)
    with Maker() as s:
        s.add(
            Repo(
                id=999,
                org="brand-new",
                name="repo",
                stars=42,
                stars_1d_ago=42,
                stars_7d_ago=42,
                forks=7,
                description="t",
                category="Tools",
                created_at=same_day,
                updated_at=same_day,
            )
        )
        s.commit()
        backfill_anchors_into(s)
        rows = s.query(RepoStarSnapshot).filter_by(repo_id=999).all()
    # 3 distinct anchor timestamps after collapse.
    assert len(rows) == 3
    # Surviving anchor at same_day must carry real forks=7, not 0.
    surviving = next(r for r in rows if r.captured_at.date() == same_day)
    assert surviving.stars == 42
    assert surviving.forks == 7


def test_chart_renders_with_anchor_backfill_only(engine: Engine) -> None:
    """End-to-end: seed + backfill, then ``/api/charts/series`` returns
    a non-empty time-series even with zero cron-written rows.

    Mirrors the live demo's no-GITHUB_TOKEN deploy path: the user
    visits ``/charts`` and sees real data points without the cron ever
    having run.
    """
    from app.routes.charts import build_series

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        backfill_anchors_into(s)
        series = build_series(s)
    # 6 categories from the seed, each with at least 1 point.
    assert len(series) == 6
    for cat_series in series:
        assert len(cat_series.points) >= 1
        assert cat_series.points[-1].stars > 0
