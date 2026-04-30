"""Shared fixtures: in-memory SQLite + FastAPI TestClient with seed data."""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app import db as db_module
from app.db import init_db, make_engine
from app.seed import seed_into


@pytest.fixture()
def engine() -> Generator[Engine, None, None]:
    eng = make_engine("sqlite:///:memory:")
    init_db(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def session(engine: Engine) -> Generator[Session, None, None]:
    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        yield s


@pytest.fixture()
def seeded_session(session: Session) -> Session:
    seed_into(session)
    return session


@pytest.fixture()
def client(engine: Engine) -> Generator[TestClient, None, None]:
    """A FastAPI TestClient backed by an in-memory DB pre-loaded with seed data."""
    from app.main import create_app  # imported here so engine override is fresh

    Maker = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    with Maker() as s:
        seed_into(s)

    app: FastAPI = create_app()

    def _override_session() -> Generator[Session, None, None]:
        with Maker() as session:
            yield session

    app.dependency_overrides[db_module.get_session] = _override_session
    with TestClient(app) as c:
        yield cast(TestClient, c)
