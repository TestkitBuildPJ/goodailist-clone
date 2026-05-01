"""Freshness helper — compute "last ingest run" + "stale" flag for templates.

The footer on every page shows when ``repo_star_snapshots`` was last
written, and a banner appears above the page content when that
timestamp is older than the configured threshold (24h by default).

Phase B: snapshots are written by the daily cron at ~03:00 UTC and on
operator-triggered ``POST /admin/refresh``.  When zero snapshots exist
yet (fresh deploy, before the first cron tick) the page shows
"No snapshots yet" instead of a stale warning, since the chart falls
back to Phase A anchor approximation in that case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import RepoStarSnapshot

STALE_THRESHOLD = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class Freshness:
    """Snapshot of how recent the latest ingest is.

    Attributes
    ----------
    last_captured_at:
        Naive UTC datetime of the most recent ``repo_star_snapshots``
        row, or ``None`` if the table is empty.
    age:
        ``now - last_captured_at`` (``None`` when no snapshots).
    is_stale:
        ``True`` when ``age > STALE_THRESHOLD``.
    has_snapshots:
        Whether at least one snapshot row exists.
    """

    last_captured_at: datetime | None
    age: timedelta | None
    is_stale: bool
    has_snapshots: bool

    @property
    def hours_ago(self) -> float | None:
        """Convenience for templates — ``None`` when no snapshots yet."""
        if self.age is None:
            return None
        return self.age.total_seconds() / 3600.0


def _utcnow_naive() -> datetime:
    """UTC ``now()`` with tzinfo stripped to match how snapshots are stored."""
    return datetime.now(tz=UTC).replace(tzinfo=None)


def compute_freshness(session: Session, *, now: datetime | None = None) -> Freshness:
    """Compute the freshness state for the current request.

    ``now`` is injectable so tests can pin "current time" — production
    code calls without it and gets ``datetime.utcnow()`` semantics.
    """
    last = session.query(func.max(RepoStarSnapshot.captured_at)).scalar()
    if last is None:
        return Freshness(
            last_captured_at=None,
            age=None,
            is_stale=False,
            has_snapshots=False,
        )

    current = now if now is not None else _utcnow_naive()
    age = current - last
    return Freshness(
        last_captured_at=last,
        age=age,
        is_stale=age > STALE_THRESHOLD,
        has_snapshots=True,
    )
