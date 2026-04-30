"""Load ``seed_data/repos.json`` into the database.

Idempotent: dropping then re-creating the ``repos`` table on every run
keeps Phase A simple — Phase B will switch to incremental upsert.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, get_engine, init_db
from app.models import Repo

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
