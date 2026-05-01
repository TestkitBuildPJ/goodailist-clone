"""Tests for :mod:`app.ingest.scheduler` wiring."""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.ingest import scheduler as sched
from app.models import IngestRun


def test_should_start_returns_true_only_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert sched.should_start() is False
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    assert sched.should_start() is True


def test_build_scheduler_uses_env_hour_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_CRON_HOUR", "5")
    monkeypatch.setenv("INGEST_CRON_MINUTE", "15")
    s = sched.build_scheduler()
    job = s.get_job("daily_ingest")
    assert job is not None
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "5"
    assert fields["minute"] == "15"


def test_build_scheduler_falls_back_when_env_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_CRON_HOUR", "not-an-int")
    s = sched.build_scheduler()
    job = s.get_job("daily_ingest")
    assert job is not None
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "3"


async def test_trigger_now_runs_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """``trigger_now`` should invoke the underlying job exactly once."""
    fired: list[bool] = []

    async def fake_run_once(**_: object) -> object:
        fired.append(True)

        class Stats:
            status = "success"
            repos_updated = 0
            api_calls = 0
            etag_hits = 0

        return Stats()

    monkeypatch.setattr("app.ingest.scheduler.run_once", fake_run_once)
    await sched.trigger_now()
    assert fired == [True]


async def test_reconcile_dangling_runs_marks_running_as_failed(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leftover ``status='running'`` row should be reconciled to ``failed``."""
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    monkeypatch.setattr("app.ingest.scheduler.get_engine", lambda: engine)

    with Maker() as s:
        s.add(IngestRun(started_at=datetime(2024, 1, 1, 3, 0), status="running"))
        s.add(IngestRun(started_at=datetime(2024, 1, 1, 3, 1), status="success"))
        s.commit()

    await sched.reconcile_dangling_runs()

    with Maker() as s:
        statuses = sorted(r.status for r in s.query(IngestRun).all())
        assert statuses == ["failed", "success"]


_ = asyncio
