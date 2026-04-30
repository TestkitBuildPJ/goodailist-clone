"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import SessionLocal, init_db
from app.models import Repo
from app.routes import charts, repos
from app.seed import seed_into

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    """Application factory used by ``uvicorn`` and tests."""
    app = FastAPI(title="goodailist-clone", version="0.1.0")

    init_db()

    # Seed once if empty so a fresh container has data on first request.
    with SessionLocal() as session:
        if session.query(Repo).count() == 0:
            seed_into(session)

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

    return app


app = create_app()
