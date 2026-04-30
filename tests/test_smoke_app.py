"""Extra smoke tests covering the full request pipeline."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_filter_and_sort_combined(client: TestClient) -> None:
    payload = client.get(
        "/api/repos",
        params={"category": "LLM", "sort": "forks", "order": "desc"},
    ).json()
    assert len(payload) >= 3
    assert all(row["category"] == "LLM" for row in payload)
    forks = [row["forks"] for row in payload]
    assert forks == sorted(forks, reverse=True)


def test_unknown_category_returns_empty(client: TestClient) -> None:
    payload = client.get("/api/repos", params={"category": "DoesNotExist"}).json()
    assert payload == []


def test_invalid_sort_rejected(client: TestClient) -> None:
    response = client.get("/api/repos", params={"sort": "bogus"})
    assert response.status_code == 422


def test_charts_series_count_matches_categories(client: TestClient) -> None:
    series = client.get("/api/charts/series").json()
    # Each series corresponds to a non-empty category in the seed set.
    categories_in_series = {s["category"] for s in series}
    repos = client.get("/api/repos").json()
    categories_in_repos = {r["category"] for r in repos}
    assert categories_in_series == categories_in_repos
