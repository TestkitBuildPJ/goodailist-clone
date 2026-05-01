"""Tests for /charts page + /api/charts/series JSON endpoint."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import db as db_module
from app.models import Repo, RepoStarSnapshot
from app.seed import seed_into


def test_charts_page_renders(client: TestClient) -> None:
    response = client.get("/charts")
    assert response.status_code == 200
    body = response.text
    assert "Cumulative Star Count Over Time" in body
    assert 'id="cum-stars"' in body
    assert 'id="series-data"' in body


def test_charts_api_returns_series(client: TestClient) -> None:
    response = client.get("/api/charts/series")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    categories = {s["category"] for s in payload}
    # all 6 canonical categories should be present in the seed set
    assert {"LLM", "Agents", "RAG", "Vector-DB", "Eval", "Tools"} <= categories


def test_charts_api_points_are_monotone(client: TestClient) -> None:
    payload = client.get("/api/charts/series").json()
    for series in payload:
        points = series["points"]
        assert len(points) >= 2
        stars_seq = [p["stars"] for p in points]
        assert stars_seq == sorted(
            stars_seq
        ), f"category {series['category']} cumulative series not monotone: {stars_seq}"


def test_charts_api_dates_are_sorted(client: TestClient) -> None:
    payload = client.get("/api/charts/series").json()
    for series in payload:
        dates = [p["date"] for p in series["points"]]
        assert dates == sorted(dates)


@pytest.fixture()
def client_with_snapshots(engine: Engine) -> Generator[TestClient, None, None]:
    """TestClient backed by a DB pre-loaded with seed data + 3 snapshots/repo."""
    from app.main import create_app

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        # write 3 daily snapshots per repo (10, 11, 12 stars-ago shifts).
        anchor = datetime(2026, 4, 28, 3, 0, tzinfo=UTC)
        for repo in s.query(Repo).all():
            base = int(repo.stars)
            for day_offset, delta in enumerate([-2, -1, 0]):
                s.add(
                    RepoStarSnapshot(
                        repo_id=repo.id,
                        captured_at=anchor + timedelta(days=day_offset),
                        stars=base + delta,
                        forks=int(repo.forks),
                    )
                )
        s.commit()

    app: FastAPI = create_app()

    def _override_session() -> Generator[Session, None, None]:
        with Maker() as session:
            yield session

    app.dependency_overrides[db_module.get_session] = _override_session
    with TestClient(app) as c:
        yield cast(TestClient, c)


def test_charts_uses_snapshots_when_available(
    client_with_snapshots: TestClient,
) -> None:
    """When snapshots exist, chart series should come from them, not anchors.

    The seeded snapshots are 3 consecutive UTC days (2026-04-28, -29, -30).
    The Phase A anchors live in 2022..2026 across many dates.  If the
    snapshot path is taken, the only dates in the response should be those
    3 days (plus possibly cold-repo anchors — but here all repos have
    snapshots so the set is exactly 3).
    """
    payload = client_with_snapshots.get("/api/charts/series").json()
    snap_dates = {"2026-04-28", "2026-04-29", "2026-04-30"}
    for series in payload:
        dates = {p["date"] for p in series["points"]}
        assert dates == snap_dates, (
            f"category {series['category']} should use snapshot dates only," f" got {dates}"
        )


def test_charts_falls_back_when_some_repos_lack_snapshots(
    engine: Engine,
) -> None:
    """If only some repos have snapshots, cold repos must still contribute via anchors."""
    from app.routes.charts import build_series

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)
        # snapshot just one repo
        first = s.query(Repo).first()
        assert first is not None
        s.add(
            RepoStarSnapshot(
                repo_id=first.id,
                captured_at=datetime(2026, 4, 30, 3, 0, tzinfo=UTC),
                stars=int(first.stars),
                forks=int(first.forks),
            )
        )
        s.commit()

    with Maker() as s:
        out = build_series(s)
    # all 6 categories still rendered (cold repos fall back to anchors).
    cats = {sr.category for sr in out}
    assert {"LLM", "Agents", "RAG", "Vector-DB", "Eval", "Tools"} <= cats
