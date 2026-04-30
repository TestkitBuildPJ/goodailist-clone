"""Tests for Phase B ORM models — ``RepoStarSnapshot`` + ``IngestRun``.

Schema-level only (no scheduler / no HTTP yet); those land in TIP-B02+.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.models import IngestRun, Repo, RepoStarSnapshot


def _make_repo(session) -> Repo:  # type: ignore[no-untyped-def]
    repo = Repo(
        id=999,
        org="acme",
        name="widget",
        stars=100,
        stars_1d_ago=99,
        stars_7d_ago=80,
        forks=10,
        description="seed",
        category="LLM",
        created_at=date(2024, 1, 1),
        updated_at=date(2024, 1, 8),
    )
    session.add(repo)
    session.commit()
    return repo


def test_snapshot_round_trip(engine: Engine) -> None:
    """A snapshot row written then read should preserve all fields."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        repo = _make_repo(s)
        captured = datetime(2024, 1, 8, 3, 0, tzinfo=UTC).replace(tzinfo=None)
        s.add(RepoStarSnapshot(repo_id=repo.id, captured_at=captured, stars=100, forks=10))
        s.commit()

    with Maker() as s:
        rows = s.query(RepoStarSnapshot).filter_by(repo_id=999).all()
        assert len(rows) == 1
        assert rows[0].stars == 100
        assert rows[0].forks == 10
        assert rows[0].captured_at.year == 2024


def test_snapshot_cascade_on_repo_delete(engine: Engine) -> None:
    """Deleting a Repo should cascade-delete its snapshots."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        repo = _make_repo(s)
        s.add_all(
            [
                RepoStarSnapshot(
                    repo_id=repo.id,
                    captured_at=datetime(2024, 1, d, 3, 0),
                    stars=100 + d,
                    forks=10,
                )
                for d in (1, 2, 3)
            ]
        )
        s.commit()

    with Maker() as s:
        repo_obj = s.get(Repo, 999)
        assert repo_obj is not None
        s.delete(repo_obj)
        s.commit()
        assert s.query(RepoStarSnapshot).filter_by(repo_id=999).count() == 0


def test_ingest_run_lifecycle(engine: Engine) -> None:
    """An IngestRun starts as ``running`` then is finalized."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    started = datetime(2024, 1, 8, 3, 0)
    with Maker() as s:
        run = IngestRun(started_at=started, status="running")
        s.add(run)
        s.commit()
        run_id = run.id

    with Maker() as s:
        run = s.get(IngestRun, run_id)
        assert run is not None
        run.status = "success"
        run.finished_at = datetime(2024, 1, 8, 3, 1)
        run.repos_updated = 30
        run.api_calls = 30
        run.etag_hits = 0
        s.commit()

    with Maker() as s:
        row = s.query(IngestRun).filter_by(id=run_id).one()
        assert row.status == "success"
        assert row.repos_updated == 30
        assert row.api_calls == 30
        assert row.etag_hits == 0
        assert row.error_msg is None


def test_ingest_run_failure_carries_error(engine: Engine) -> None:
    """Failed runs should preserve error_msg."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        s.add(
            IngestRun(
                started_at=datetime(2024, 1, 8, 3, 0),
                finished_at=datetime(2024, 1, 8, 3, 0, 5),
                status="failed",
                error_msg="upstream 503",
            )
        )
        s.commit()
    with Maker() as s:
        row = s.query(IngestRun).filter_by(status="failed").one()
        assert row.error_msg == "upstream 503"
