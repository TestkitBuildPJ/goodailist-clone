"""Tests for the Repo model + computed properties."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import Repo


def test_full_name_property() -> None:
    repo = Repo(
        id=1,
        org="langchain-ai",
        name="langchain",
        stars=100,
        stars_1d_ago=90,
        stars_7d_ago=80,
        forks=5,
        description="",
        category="Agents",
        created_at=date(2022, 1, 1),
        updated_at=date(2026, 4, 30),
    )
    assert repo.full_name == "langchain-ai/langchain"


def test_delta_properties() -> None:
    repo = Repo(
        id=2,
        org="x",
        name="y",
        stars=200,
        stars_1d_ago=190,
        stars_7d_ago=150,
        forks=0,
        description="",
        category="LLM",
        created_at=date(2020, 1, 1),
        updated_at=date(2026, 4, 30),
    )
    assert repo.stars_1d_delta == 10
    assert repo.stars_7d_delta == 50


def test_repo_persists_round_trip(session: Session) -> None:
    repo = Repo(
        id=99,
        org="test",
        name="proj",
        stars=42,
        stars_1d_ago=40,
        stars_7d_ago=30,
        forks=3,
        description="hello",
        category="Tools",
        created_at=date(2024, 6, 1),
        updated_at=date(2026, 4, 30),
    )
    session.add(repo)
    session.commit()
    session.expire_all()
    fetched = session.get(Repo, 99)
    assert fetched is not None
    assert fetched.full_name == "test/proj"
    assert fetched.stars_1d_delta == 2
