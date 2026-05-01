"""Unit tests for :mod:`app.ingest.etag_store`."""

from __future__ import annotations

from app.ingest.etag_store import EtagStore


def test_set_then_get_round_trip() -> None:
    store = EtagStore()
    store.set("acme", "widget", '"abc123"')
    assert store.get("acme", "widget") == '"abc123"'


def test_get_returns_none_for_unknown_repo() -> None:
    store = EtagStore()
    assert store.get("acme", "missing") is None


def test_set_empty_etag_is_ignored() -> None:
    store = EtagStore()
    store.set("acme", "widget", "")
    assert store.get("acme", "widget") is None


def test_clear_drops_all_entries() -> None:
    store = EtagStore()
    store.set("a", "x", "e1")
    store.set("b", "y", "e2")
    assert len(store) == 2
    store.clear()
    assert len(store) == 0
    assert store.get("a", "x") is None


def test_distinct_owners_keep_separate_entries() -> None:
    store = EtagStore()
    store.set("acme", "widget", '"e1"')
    store.set("globex", "widget", '"e2"')
    assert store.get("acme", "widget") == '"e1"'
    assert store.get("globex", "widget") == '"e2"'
