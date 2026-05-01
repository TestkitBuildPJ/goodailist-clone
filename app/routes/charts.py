"""``/charts`` page + ``/api/charts/series`` JSON endpoint.

When the ``repo_star_snapshots`` table holds at least one row, the chart
is built from real time-series data: per-repo daily snapshots are summed
into a per-category cumulative-stars line.  Repos without snapshots fall
back to the Phase A anchor approximation so the chart still renders on a
fresh deploy before the first cron tick lands.

Phase A anchors per repo:

- ``created_at``           → 0 stars (seeded baseline)
- ``updated_at - 7 days``  → ``stars_7d_ago``
- ``updated_at - 1 day``   → ``stars_1d_ago``
- ``updated_at``           → ``stars``
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Repo, RepoStarSnapshot
from app.routes.repos import CATEGORIES
from app.schemas import ChartPoint, ChartSeries

router = APIRouter()


def _anchor_series(repos: list[Repo]) -> dict[str, dict[date, int]]:
    """Phase A fallback: synthesise per-(category, date) sums from anchors."""
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
    return by_category


def _snapshot_series(session: Session, repos: list[Repo]) -> dict[str, dict[date, int]]:
    """Phase B path: aggregate ``repo_star_snapshots`` into per-(category, date) sums.

    Repos that have not been ingested yet are filled in from their anchor
    approximation so the chart never has gaps.
    """
    by_category: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    repos_with_snapshots: set[int] = set()

    for snap, repo in (
        session.query(RepoStarSnapshot, Repo)
        .join(Repo, RepoStarSnapshot.repo_id == Repo.id)
        .order_by(RepoStarSnapshot.captured_at)
        .all()
    ):
        repos_with_snapshots.add(int(repo.id))
        d = snap.captured_at.date()
        by_category[repo.category][d] += int(snap.stars)

    # Repos with zero snapshots: fall back to anchors so they still contribute.
    cold_repos = [r for r in repos if int(r.id) not in repos_with_snapshots]
    if cold_repos:
        for cat, by_date in _anchor_series(cold_repos).items():
            for d, v in by_date.items():
                by_category[cat][d] += v

    return by_category


def _running_max(by_date: dict[date, int]) -> list[ChartPoint]:
    """Convert (date → stars) into a non-decreasing list of ChartPoints.

    A daily aggregate may dip transiently if a repo missed an ingest tick;
    presenting a "cumulative" chart that goes down would mislead users, so
    we clamp to the running max.
    """
    ordered = sorted(by_date.items())
    running = 0
    points: list[ChartPoint] = []
    for d, val in ordered:
        running = max(running, val)
        points.append(ChartPoint(date=d, stars=running))
    return points


def build_series(session: Session) -> list[ChartSeries]:
    """Public helper used by the page route + the API."""
    repos = list(session.query(Repo).all())
    has_snapshots = session.query(RepoStarSnapshot.id).first() is not None
    raw = _snapshot_series(session, repos) if has_snapshots else _anchor_series(repos)

    out: list[ChartSeries] = []
    for cat in CATEGORIES:
        if cat in raw:
            out.append(ChartSeries(category=cat, points=_running_max(raw[cat])))
    for cat, by_date in raw.items():
        if cat not in CATEGORIES:
            out.append(ChartSeries(category=cat, points=_running_max(by_date)))
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
