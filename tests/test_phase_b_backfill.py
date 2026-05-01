"""Tests for the ``0003_phase_b_backfill`` Alembic data migration.

The migration synthesises 4 snapshot rows per existing repo (Phase A
anchor points) into ``repo_star_snapshots`` so ``/charts`` can render a
real time-series view immediately after deploy without waiting for the
first cron tick.

These tests run the migration's ``upgrade()`` / ``downgrade()`` callables
directly against an in-memory SQLite DB pre-populated by the standard
seed.  We don't go through the alembic CLI to keep the suite hermetic
and fast.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Repo, RepoStarSnapshot
from app.seed import seed_into


def _import_backfill_module():  # type: ignore[no-untyped-def]
    """Load the migration module directly from disk (alembic doesn't expose it as a regular package)."""
    import importlib.util
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    target = next(p for p in here.glob("*.py") if "phase_b_backfill" in p.name)
    spec = importlib.util.spec_from_file_location("_backfill_under_test", target)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def migrated_engine() -> Generator[Engine, None, None]:
    """Engine with both ORM tables created and Phase A seed loaded.

    The migration code uses ``alembic.op``, which needs an active
    ``MigrationContext`` bound to a SQLAlchemy connection.  We bind one
    manually here so the migration file's ``upgrade()`` / ``downgrade()``
    can run against this engine without invoking the alembic CLI.
    """
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)

    Maker = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)

    yield eng
    eng.dispose()


def _run_in_migration_context(eng: Engine, fn_name: str) -> None:
    """Execute the named migration entrypoint against a live engine."""
    mod = _import_backfill_module()
    with eng.begin() as conn:
        ctx = MigrationContext.configure(conn)
        # ``alembic.op`` is a global proxy bound by Operations.context().
        with Operations.context(ctx):
            getattr(mod, fn_name)()


def test_backfill_writes_four_anchors_per_repo(migrated_engine: Engine) -> None:
    """Fresh seed → 30 repos → 30 × 4 = 120 snapshot rows after upgrade.

    Repos whose ``created_at`` collides with one of the other three
    anchors will produce fewer than 4 distinct rows; the canonical seed
    has well-separated anchors so we expect the full 120.
    """
    _run_in_migration_context(migrated_engine, "upgrade")

    Maker = sessionmaker(bind=migrated_engine, future=True)
    with Maker() as s:
        n_repos = s.query(Repo).count()
        n_snaps = s.query(RepoStarSnapshot).count()
    assert n_repos == 30
    assert n_snaps == 30 * 4


def test_backfill_is_idempotent(migrated_engine: Engine) -> None:
    """Running the migration twice should leave the row count unchanged."""
    _run_in_migration_context(migrated_engine, "upgrade")
    _run_in_migration_context(migrated_engine, "upgrade")  # second time — no-op

    Maker = sessionmaker(bind=migrated_engine, future=True)
    with Maker() as s:
        assert s.query(RepoStarSnapshot).count() == 30 * 4


def test_backfill_downgrade_removes_only_synthetic_rows(
    migrated_engine: Engine,
) -> None:
    """Downgrade should clear all anchor rows but preserve cron-written ones.

    Simulate a real cron-written snapshot by inserting one row with a
    timestamp that is NOT one of the four computed anchor dates.  After
    downgrade, only that row should remain.
    """
    _run_in_migration_context(migrated_engine, "upgrade")

    # Insert a "real cron" snapshot at a timestamp the migration cannot
    # have produced (any minute != 03:00 makes it distinguishable).
    Maker = sessionmaker(bind=migrated_engine, future=True)
    with Maker() as s:
        s.add(
            RepoStarSnapshot(
                repo_id=1,
                captured_at=datetime(2026, 5, 1, 12, 34),  # 12:34, not 03:00
                stars=12345,
                forks=99,
            )
        )
        s.commit()
        before = s.query(RepoStarSnapshot).count()
    assert before == 30 * 4 + 1

    _run_in_migration_context(migrated_engine, "downgrade")

    with Maker() as s:
        rows = s.query(RepoStarSnapshot).all()
    # The single real-cron row should survive; all 120 anchors gone.
    assert len(rows) == 1
    assert rows[0].stars == 12345


def test_backfill_current_anchor_keeps_real_forks_when_dates_collide() -> None:
    """When ``updated_at == created_at``, the surviving anchor must keep real forks.

    Regression: previously ``forks`` was selected via
    ``forks if ts != created_dt else 0``.  When ``created_dt == updated_dt``
    (a brand-new repo with no updates), the dict-overwrite step caused the
    final "current" row to land at ``ts == created_dt`` and the conditional
    set forks=0 instead of the actual fork count.
    """
    from datetime import date as _date

    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    Maker = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False, future=True)
    same_day = _date(2026, 4, 30)
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

    _run_in_migration_context(eng, "upgrade")

    with eng.connect() as conn:
        snaps = conn.execute(
            text(
                "SELECT captured_at, stars, forks FROM repo_star_snapshots"
                " WHERE repo_id=999 ORDER BY captured_at, stars"
            )
        ).all()
    # 3 distinct anchor timestamps (created==updated collapse): -7d, -1d, and
    # created/updated.  The surviving "current" anchor at created_dt must
    # carry real forks=7 (overwriting the 0-forks baseline that came first).
    captured_dates = [s.captured_at for s in snaps]
    assert captured_dates == sorted(captured_dates)
    surviving_current = next(s for s in snaps if str(s.captured_at).startswith("2026-04-30"))
    assert surviving_current.stars == 42
    assert surviving_current.forks == 7  # NOT 0 — that was the bug


def test_backfill_downgrade_preserves_real_snapshot_at_anchor_timestamp() -> None:
    """Downgrade must not delete a real snapshot whose timestamp coincides
    with an anchor but whose ``forks`` differs from ``repos.forks``.

    Regression: previously ``downgrade()`` only filtered on ``repo_id`` and
    ``captured_at``, ignoring the documented ``forks`` filter.  A real
    snapshot row that happened to land exactly at an anchor timestamp
    (eg. an admin refresh fired at 03:00 UTC) would be silently removed.
    """
    from datetime import date as _date

    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    Maker = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        s.add(
            Repo(
                id=42,
                org="o",
                name="n",
                stars=1000,
                stars_1d_ago=900,
                stars_7d_ago=500,
                forks=50,
                description="t",
                category="Tools",
                created_at=_date(2026, 1, 1),
                updated_at=_date(2026, 4, 30),
            )
        )
        s.commit()

    _run_in_migration_context(eng, "upgrade")

    # Real snapshot at the exact updated_dt anchor with a *different* forks
    # value than the repo's current forks (50).  This represents a real
    # cron/admin write that simulators would not delete on rollback.
    with Maker() as s:
        s.add(
            RepoStarSnapshot(
                repo_id=42,
                captured_at=datetime(2026, 4, 30, 3, 0),  # collides with updated_dt anchor
                stars=1234,
                forks=999,  # NOT 50
            )
        )
        s.commit()

    _run_in_migration_context(eng, "downgrade")

    with Maker() as s:
        rows = s.query(RepoStarSnapshot).filter_by(repo_id=42).all()
    # The 4 anchor rows are gone, but the real (forks=999) row survives.
    assert len(rows) == 1
    assert rows[0].forks == 999
    assert rows[0].stars == 1234


def test_backfill_anchor_values_match_repo_columns(migrated_engine: Engine) -> None:
    """Each repo's anchor rows must carry the values from its Phase A columns."""
    _run_in_migration_context(migrated_engine, "upgrade")

    with migrated_engine.connect() as conn:
        # Pick repo id=1 (langchain) and verify its 4 anchors.
        repo = conn.execute(
            text(
                "SELECT id, created_at, updated_at, stars, stars_1d_ago,"
                " stars_7d_ago, forks FROM repos WHERE id=1"
            )
        ).one()
        snaps = conn.execute(
            text(
                "SELECT captured_at, stars, forks FROM repo_star_snapshots"
                " WHERE repo_id=1 ORDER BY captured_at"
            )
        ).all()
    assert len(snaps) == 4
    # First anchor = created_at, 0 stars (baseline).
    assert snaps[0].stars == 0
    # Last anchor = current stars.
    assert snaps[-1].stars == int(repo.stars)
    # Middle two anchors should be stars_7d_ago / stars_1d_ago in that order.
    assert snaps[1].stars == int(repo.stars_7d_ago)
    assert snaps[2].stars == int(repo.stars_1d_ago)
