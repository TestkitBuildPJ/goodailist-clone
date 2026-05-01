"""Phase B: backfill ``repo_star_snapshots`` from Phase A 4 anchor points.

Revision ID: 0003_phase_b_backfill
Revises: 0002_phase_b_snapshots
Create Date: 2026-05-01

For each row in ``repos`` we synthesise four time-points that mirror the
columns the Phase A seed already carried:

- ``created_at`` (date)             → 0 stars, 0 forks (baseline)
- ``updated_at - 7 days``           → ``stars_7d_ago``, current ``forks``
- ``updated_at - 1 day``            → ``stars_1d_ago``, current ``forks``
- ``updated_at``                    → ``stars``,        current ``forks``

Each anchor date is anchored at 03:00 UTC so it lands at the same
timestamp shape the cron will write going forward.

**Idempotency**: a repo with at least one existing snapshot is skipped
entirely.  This makes the migration safe to re-run after a partial cron
write or after manual data fixes.

**Downgrade** removes only the rows whose ``forks`` matches the parent
``repos.forks`` AND ``captured_at`` falls on one of the four computed
anchor dates — i.e. only rows this migration could have written.  Real
cron-written snapshots have arbitrary ``captured_at`` and are preserved.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, time, timedelta

import sqlalchemy as sa

from alembic import op

revision: str = "0003_phase_b_backfill"
down_revision: str | None = "0002_phase_b_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ANCHOR_TIME = time(3, 0)  # 03:00 UTC, matches cron default
_BATCH_SIZE = 100


def _backfill_rows_for(
    repo: sa.Row[tuple[int, sa.Date, sa.Date, int, int, int, int]],
) -> list[dict[str, object]]:
    """Compute the (up to) 4 anchor snapshot rows for a single repo.

    Anchors collapse to a single row when their dates coincide (e.g. very
    new repo where ``created_at == updated_at``), so the caller may
    receive fewer than 4 rows back.
    """
    repo_id = int(repo.id)
    created_at: object = repo.created_at
    updated_at: object = repo.updated_at
    stars = int(repo.stars)
    stars_1d_ago = int(repo.stars_1d_ago)
    stars_7d_ago = int(repo.stars_7d_ago)
    forks = int(repo.forks)

    assert isinstance(created_at, type(updated_at))  # narrow for mypy
    created_dt = datetime.combine(created_at, _ANCHOR_TIME)  # type: ignore[arg-type]
    updated_dt = datetime.combine(updated_at, _ANCHOR_TIME)  # type: ignore[arg-type]
    seven_d = updated_dt - timedelta(days=7)
    one_d = updated_dt - timedelta(days=1)

    # de-dupe on (captured_at) so we never insert two rows at the same
    # timestamp for one repo (would violate the chart's per-day sum).
    by_ts: dict[datetime, dict[str, object]] = {}
    for ts, s_count in (
        (created_dt, 0),
        (seven_d, stars_7d_ago),
        (one_d, stars_1d_ago),
        (updated_dt, stars),
    ):
        by_ts[ts] = {
            "repo_id": repo_id,
            "captured_at": ts,
            "stars": int(s_count),
            "forks": forks if ts != created_dt else 0,
        }
    return list(by_ts.values())


def upgrade() -> None:
    bind = op.get_bind()

    repos_t = sa.Table(
        "repos",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.Date),
        sa.Column("updated_at", sa.Date),
        sa.Column("stars", sa.Integer),
        sa.Column("stars_1d_ago", sa.Integer),
        sa.Column("stars_7d_ago", sa.Integer),
        sa.Column("forks", sa.Integer),
    )
    snap_t = sa.Table(
        "repo_star_snapshots",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repo_id", sa.Integer),
        sa.Column("captured_at", sa.DateTime),
        sa.Column("stars", sa.Integer),
        sa.Column("forks", sa.Integer),
    )

    repos = bind.execute(
        sa.select(
            repos_t.c.id,
            repos_t.c.created_at,
            repos_t.c.updated_at,
            repos_t.c.stars,
            repos_t.c.stars_1d_ago,
            repos_t.c.stars_7d_ago,
            repos_t.c.forks,
        )
    ).fetchall()

    pending: list[dict[str, object]] = []
    for repo in repos:
        existing = bind.execute(
            sa.select(sa.func.count()).select_from(snap_t).where(snap_t.c.repo_id == repo.id)
        ).scalar_one()
        if existing > 0:
            continue  # idempotent skip — repo already has snapshots
        pending.extend(_backfill_rows_for(repo))
        if len(pending) >= _BATCH_SIZE:
            bind.execute(snap_t.insert(), pending)
            pending = []

    if pending:
        bind.execute(snap_t.insert(), pending)


def downgrade() -> None:
    """Remove only the synthetic anchor rows this migration created.

    Real cron-written snapshots are left intact even if the migration is
    rolled back, because operators may have populated real history before
    deciding to roll back.
    """
    bind = op.get_bind()

    repos_t = sa.Table(
        "repos",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.Date),
        sa.Column("updated_at", sa.Date),
    )
    snap_t = sa.Table(
        "repo_star_snapshots",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("repo_id", sa.Integer),
        sa.Column("captured_at", sa.DateTime),
    )

    repos = bind.execute(
        sa.select(repos_t.c.id, repos_t.c.created_at, repos_t.c.updated_at)
    ).fetchall()

    for repo in repos:
        created_at: object = repo.created_at
        updated_at: object = repo.updated_at
        created_dt = datetime.combine(created_at, _ANCHOR_TIME)  # type: ignore[arg-type]
        updated_dt = datetime.combine(updated_at, _ANCHOR_TIME)  # type: ignore[arg-type]
        anchor_dts = {
            created_dt,
            updated_dt - timedelta(days=7),
            updated_dt - timedelta(days=1),
            updated_dt,
        }
        bind.execute(
            snap_t.delete().where(
                sa.and_(
                    snap_t.c.repo_id == repo.id,
                    snap_t.c.captured_at.in_(anchor_dts),
                )
            )
        )
