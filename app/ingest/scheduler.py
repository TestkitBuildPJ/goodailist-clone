"""APScheduler wiring for the daily ingest cron.

Mounted in :func:`app.main.create_app` via FastAPI's lifespan handler.
Default trigger: 03:00 UTC daily (off-peak GitHub).  Can be customised via
``INGEST_CRON_HOUR`` / ``INGEST_CRON_MINUTE`` env vars.

When ``GITHUB_TOKEN`` is unset, the scheduler refuses to start and logs a
single warning — keeps the app booting normally on developer laptops.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import sessionmaker

from app.db import get_engine
from app.ingest.etag_store import EtagStore
from app.ingest.ingestor import run_once
from app.models import IngestRun

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Module-level singletons so /admin/refresh can reuse the same store.
ETAG_STORE = EtagStore()


def _hour() -> int:
    raw = os.environ.get("INGEST_CRON_HOUR", "3")
    try:
        value = int(raw)
    except ValueError:
        return 3
    return value if 0 <= value <= 23 else 3


def _minute() -> int:
    raw = os.environ.get("INGEST_CRON_MINUTE", "0")
    try:
        value = int(raw)
    except ValueError:
        return 0
    return value if 0 <= value <= 59 else 0


async def _job() -> None:
    """The actual cron callback — wraps :func:`run_once` with logging."""
    try:
        stats = await run_once(store=ETAG_STORE)
        logger.info(
            "ingest tick done: status=%s repos=%d api=%d etag_hits=%d",
            stats.status,
            stats.repos_updated,
            stats.api_calls,
            stats.etag_hits,
        )
    except Exception:  # noqa: BLE001 — boundary log; APScheduler swallows otherwise
        logger.exception("ingest tick raised an unexpected exception")


def build_scheduler(
    *,
    hour: int | None = None,
    minute: int | None = None,
    job: Callable[[], Awaitable[None]] | None = None,
) -> AsyncIOScheduler:
    """Construct an :class:`AsyncIOScheduler` with the daily ingest job.

    The scheduler is **not** started here — the caller (FastAPI lifespan)
    is responsible so the loop is the right one.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        job or _job,
        CronTrigger(
            hour=hour if hour is not None else _hour(),
            minute=minute if minute is not None else _minute(),
            timezone="UTC",
        ),
        id="daily_ingest",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


def should_start() -> bool:
    """Return True when the cron should actually run.

    The scheduler stays dormant on dev machines / CI to avoid hammering
    GitHub from places that don't have a token configured.
    """
    return bool(os.environ.get("GITHUB_TOKEN"))


async def trigger_now() -> None:
    """Run one tick immediately, regardless of cron — used by /admin/refresh."""
    await _job()


def safe_start(scheduler: AsyncIOScheduler) -> None:
    """Start the scheduler, swallowing the case where no event loop exists yet."""
    try:
        scheduler.start()
    except RuntimeError as exc:  # pragma: no cover — defensive
        logger.warning("scheduler.start failed: %s", exc)


async def reconcile_dangling_runs() -> None:
    """Mark any ``running`` rows from a previous crash as ``failed``.

    Called once on startup so dashboards never show a phantom in-progress run.
    """
    maker = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)

    def _do() -> int:
        with maker() as session:
            stale = session.query(IngestRun).filter(IngestRun.status == "running").all()
            for row in stale:
                row.status = "failed"
                row.error_msg = "process restarted before this run finished"
            session.commit()
            return len(stale)

    n = await asyncio.to_thread(_do)
    if n:
        logger.info("reconciled %d dangling ingest runs", n)
