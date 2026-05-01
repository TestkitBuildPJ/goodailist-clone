"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal, init_db
from app.ingest.scheduler import (
    build_scheduler,
    reconcile_dangling_runs,
    safe_start,
    should_start,
)
from app.models import Repo, RepoStarSnapshot
from app.routes import admin, charts, repos
from app.seed import backfill_anchors_into, seed_into

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mount + tear down the ingest scheduler.

    Stays inert when ``GITHUB_TOKEN`` is unset (dev / CI / tests).
    """
    scheduler = None
    if should_start():
        await reconcile_dangling_runs()
        scheduler = build_scheduler()
        safe_start(scheduler)
        app.state.scheduler = scheduler
        logger.info("ingest scheduler armed")
    else:
        logger.info("ingest scheduler dormant — GITHUB_TOKEN not set")
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    """Application factory used by ``uvicorn`` and tests."""
    app = FastAPI(title="goodailist-clone", version="0.2.0", lifespan=_lifespan)

    init_db()

    # Seed once if empty so a fresh container has data on first request.
    # Also synthesise the 4 Phase A anchor snapshots if no snapshot row
    # exists yet — gives ``/charts`` a real time-series even before the
    # first cron tick lands (or when running without a GITHUB_TOKEN).
    with SessionLocal() as session:
        if session.query(Repo).count() == 0:
            seed_into(session)
        if session.query(RepoStarSnapshot.id).first() is None:
            backfill_anchors_into(session)

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    if STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/repos")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(repos.router)
    app.include_router(charts.router)
    app.include_router(admin.router)

    return app


app = create_app()
