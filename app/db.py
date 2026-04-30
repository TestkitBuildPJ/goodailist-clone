"""Database engine + session factory.

Default URL is a file-backed SQLite at ``goodailist.db`` in the project
root.  Tests override via :func:`make_engine` (in-memory + ``StaticPool``).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Common SQLAlchemy declarative base."""


DEFAULT_URL = os.environ.get("GOODAILIST_DB_URL", "sqlite:///goodailist.db")

_engine: Engine = create_engine(
    DEFAULT_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if DEFAULT_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)


def make_engine(url: str = "sqlite:///:memory:") -> Engine:
    """Create a fresh engine — used by tests for isolated databases."""
    connect_args: dict[str, object] = {}
    poolclass = None
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        poolclass = StaticPool
    return create_engine(
        url,
        echo=False,
        future=True,
        connect_args=connect_args,
        poolclass=poolclass,
    )


def init_db(engine: Engine | None = None) -> Engine:
    """Create all tables on the supplied (or default) engine."""
    eng = engine if engine is not None else _engine
    # Import models here so SQLAlchemy registers tables on the metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(eng)
    return eng


def get_engine() -> Engine:
    """Return the module-level engine (overridable via dependency injection)."""
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a SQLAlchemy session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
