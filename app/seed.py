"""Load ``seed_data/repos.json`` into the database.

Idempotent: dropping then re-creating the ``repos`` table on every run
keeps Phase A simple — Phase B will switch to incremental upsert.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, get_engine, init_db
from app.models import Repo, RepoStarSnapshot

SEED_PATH = Path(__file__).resolve().parent.parent / "seed_data" / "repos.json"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _row_from_dict(payload: dict[str, Any]) -> Repo:
    return Repo(
        id=int(payload["id"]),
        org=str(payload["org"]),
        name=str(payload["name"]),
        stars=int(payload["stars"]),
        stars_1d_ago=int(payload["stars_1d_ago"]),
        stars_7d_ago=int(payload["stars_7d_ago"]),
        forks=int(payload["forks"]),
        description=str(payload.get("description", "")),
        category=str(payload["category"]),
        created_at=_parse_date(str(payload["created_at"])),
        updated_at=_parse_date(str(payload["updated_at"])),
    )


def load_seed_payload(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    """Read and parse the seed JSON file."""
    raw = path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError(f"seed file {path} must contain a top-level JSON array")
    return [dict(item) for item in parsed]


def seed_into(session: Session, payload: list[dict[str, Any]] | None = None) -> int:
    """Insert ``payload`` (or the default seed file) into ``session``.

    Returns the number of rows written.  Existing ``repos`` are wiped first.
    """
    rows = payload if payload is not None else load_seed_payload()
    session.query(Repo).delete()
    repos = [_row_from_dict(item) for item in rows]
    session.add_all(repos)
    session.commit()
    return len(repos)


_BACKFILL_ANCHOR_TIME = time(3, 0)  # 03:00 UTC, matches cron default


def backfill_anchors_into(session: Session) -> int:
    """Synthesise 4 ``repo_star_snapshots`` rows per repo from Phase A anchors.

    Mirrors the ``0003_phase_b_backfill`` Alembic migration but runs
    against an ORM session so we can call it directly at startup
    without invoking the alembic CLI.  Same idempotency guarantees:
    repos that already have at least one snapshot row are skipped.

    Returns the number of snapshot rows actually inserted.
    """
    from sqlalchemy import select

    repos_with_snapshots: set[int] = set(
        session.scalars(select(RepoStarSnapshot.repo_id).distinct()).all()
    )
    inserted = 0
    for repo in session.query(Repo).all():
        if int(repo.id) in repos_with_snapshots:
            continue
        forks = int(repo.forks)
        created_dt = datetime.combine(repo.created_at, _BACKFILL_ANCHOR_TIME)
        updated_dt = datetime.combine(repo.updated_at, _BACKFILL_ANCHOR_TIME)
        # Same dedupe-by-timestamp rule as migration 0003: collapse anchors
        # whose computed datetime collides into a single row.
        by_ts: dict[datetime, tuple[int, int]] = {}
        for ts, s_count, f_count in (
            (created_dt, 0, 0),
            (updated_dt - timedelta(days=7), int(repo.stars_7d_ago), forks),
            (updated_dt - timedelta(days=1), int(repo.stars_1d_ago), forks),
            (updated_dt, int(repo.stars), forks),
        ):
            by_ts[ts] = (s_count, f_count)
        for ts, (s_count, f_count) in by_ts.items():
            session.add(
                RepoStarSnapshot(
                    repo_id=int(repo.id),
                    captured_at=ts,
                    stars=s_count,
                    forks=f_count,
                )
            )
            inserted += 1
    session.commit()
    return inserted


def reset_and_seed(engine: Engine | None = None) -> int:
    """Drop+create tables on ``engine`` then seed the default payload."""
    eng = engine if engine is not None else get_engine()
    Base.metadata.drop_all(eng)
    init_db(eng)
    with SessionLocal(bind=eng) as session:
        return seed_into(session)


def main() -> None:
    count = reset_and_seed()
    print(f"Seeded {count} repos from {SEED_PATH}")


if __name__ == "__main__":
    main()
