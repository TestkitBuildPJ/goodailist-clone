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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from alembic.migration import MigrationContext
from alembic.operations import Operations
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
