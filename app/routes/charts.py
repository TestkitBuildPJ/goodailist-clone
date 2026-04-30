"""``/charts`` page + ``/api/charts/series`` JSON endpoint.

Phase A approximates the cumulative-star series by sampling at three
anchor dates per repo:

- ``created_at``           → 0 stars (seeded baseline)
- ``updated_at - 7 days``  → ``stars_7d_ago``
- ``updated_at - 1 day``   → ``stars_1d_ago``
- ``updated_at``           → ``stars``

For each category we sum across repos at each anchor date.  Phase B
will replace this with a real time-series ingest.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Repo
from app.routes.repos import CATEGORIES
from app.schemas import ChartPoint, ChartSeries

router = APIRouter()


def _category_series(repos: list[Repo]) -> dict[str, list[ChartPoint]]:
    """Aggregate repos into per-category cumulative star points."""
    by_category: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))

    for repo in repos:
        anchors: list[tuple[date, int]] = [
            (repo.created_at, 0),
            (repo.updated_at - timedelta(days=7), repo.stars_7d_ago),
            (repo.updated_at - timedelta(days=1), repo.stars_1d_ago),
            (repo.updated_at, repo.stars),
        ]
        for anchor_date, anchor_stars in anchors:
            by_category[repo.category][anchor_date] += anchor_stars

    series: dict[str, list[ChartPoint]] = {}
    for cat, by_date in by_category.items():
        ordered = sorted(by_date.items())
        running = 0
        points: list[ChartPoint] = []
        for d, val in ordered:
            running = max(running, val)
            points.append(ChartPoint(date=d, stars=running))
        series[cat] = points
    return series


def build_series(session: Session) -> list[ChartSeries]:
    """Public helper used by the page route + the API."""
    repos = list(session.query(Repo).all())
    raw = _category_series(repos)
    out: list[ChartSeries] = []
    for cat in CATEGORIES:
        if cat in raw:
            out.append(ChartSeries(category=cat, points=raw[cat]))
    # include any extra categories that appeared in seed data but aren't enum
    for cat, points in raw.items():
        if cat not in CATEGORIES:
            out.append(ChartSeries(category=cat, points=points))
    return out


@router.get("/charts", response_class=HTMLResponse)
def charts_page(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    series = build_series(session)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "charts.html",
        {
            "series": [s.model_dump(mode="json") for s in series],
        },
    )


@router.get("/api/charts/series", response_model=list[ChartSeries])
def charts_api(
    session: Session = Depends(get_session),
) -> list[ChartSeries]:
    return build_series(session)
