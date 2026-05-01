"""Tests for /admin/refresh and /admin/runs.

The admin router is gated by ``X-Admin-Token``; tests inject the env var
via monkeypatch and exercise both happy and unhappy paths.

The actual GitHub HTTP layer is mocked via ``respx`` so ``run_once``
returns deterministic results.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import db as db_module
from app.ingest.github_client import GITHUB_API
from app.main import create_app
from app.models import IngestRun, Repo
from app.seed import seed_into

ADMIN_TOKEN = "test-admin-token"


@pytest.fixture()
def admin_client(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient where ``ADMIN_TOKEN`` is set and DB deps point at ``engine``."""
    monkeypatch.setenv("ADMIN_TOKEN", ADMIN_TOKEN)

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)

    app: FastAPI = create_app()

    def _override_session():  # type: ignore[no-untyped-def]
        with Maker() as session:
            yield session

    def _override_engine() -> Engine:
        return engine

    app.dependency_overrides[db_module.get_session] = _override_session
    app.dependency_overrides[db_module.get_engine] = _override_engine
    return cast(TestClient, TestClient(app))


def test_refresh_without_token_returns_401(admin_client: TestClient) -> None:
    r = admin_client.post("/admin/refresh")
    assert r.status_code == 401
    assert "X-Admin-Token" in r.json()["detail"]


def test_refresh_with_wrong_token_returns_401(admin_client: TestClient) -> None:
    r = admin_client.post("/admin/refresh", headers={"X-Admin-Token": "nope"})
    assert r.status_code == 401


def test_runs_without_token_returns_401(admin_client: TestClient) -> None:
    r = admin_client.get("/admin/runs")
    assert r.status_code == 401


def test_admin_routes_fail_closed_when_env_unset(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    # Even with the *correct* token from before, no env → 401.
    r = admin_client.post("/admin/refresh", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 401


@respx.mock
def test_refresh_runs_one_tick_and_returns_stats(admin_client: TestClient, engine: Engine) -> None:
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        owners = [(r.id, r.org, r.name) for r in s.query(Repo).all()]
    for _id, owner, name in owners:
        respx.get(f"{GITHUB_API}/repos/{owner}/{name}").mock(
            return_value=httpx.Response(
                200,
                json={"stargazers_count": 7, "forks_count": 1},
                headers={"ETag": f'"{owner}"'},
            )
        )

    r = admin_client.post("/admin/refresh", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "success"
    assert body["repos_updated"] == len(owners)
    assert body["run_id"] is not None

    with Maker() as s:
        run = s.get(IngestRun, body["run_id"])
        assert run is not None
        assert run.status == "success"


def test_runs_returns_recent_runs_descending(admin_client: TestClient, engine: Engine) -> None:
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        for i in range(3):
            s.add(
                IngestRun(
                    started_at=datetime(2024, 1, 1, 3, i),
                    status="success",
                    repos_updated=10 + i,
                    api_calls=10 + i,
                    etag_hits=i,
                )
            )
        s.commit()

    r = admin_client.get("/admin/runs", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert isinstance(payload, list)
    assert len(payload) == 3
    # Newest first.
    ids = [row["id"] for row in payload]
    assert ids == sorted(ids, reverse=True)
    assert payload[0]["status"] == "success"
    assert payload[0]["repos_updated"] == 12


def test_runs_respects_limit(admin_client: TestClient, engine: Engine) -> None:
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        for i in range(5):
            s.add(IngestRun(started_at=datetime(2024, 1, 1, 3, i), status="success"))
        s.commit()

    r = admin_client.get("/admin/runs?limit=2", headers={"X-Admin-Token": ADMIN_TOKEN})
    assert r.status_code == 200
    assert len(r.json()) == 2


_ = Session
