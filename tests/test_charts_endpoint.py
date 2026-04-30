"""Tests for /charts page + /api/charts/series JSON endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
