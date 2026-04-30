"""Tests for the seed loader."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Repo
from app.seed import SEED_PATH, load_seed_payload, seed_into


def test_seed_file_has_30_repos() -> None:
    payload = load_seed_payload()
    assert len(payload) == 30, f"expected 30 seed repos, got {len(payload)}"


def test_seed_categories_are_canonical() -> None:
    payload = load_seed_payload()
    allowed = {"LLM", "Agents", "RAG", "Vector-DB", "Eval", "Tools"}
    seen = {item["category"] for item in payload}
    assert seen <= allowed, f"unknown categories present: {seen - allowed}"


def test_seed_into_inserts_rows(session: Session) -> None:
    count = seed_into(session)
    assert count == 30
    assert session.query(Repo).count() == 30


def test_seed_is_idempotent(session: Session) -> None:
    seed_into(session)
    seed_into(session)
    assert session.query(Repo).count() == 30


def test_seed_path_is_a_file() -> None:
    assert SEED_PATH.is_file(), f"{SEED_PATH} not found"
