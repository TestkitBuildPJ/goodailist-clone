"""Tests for /repos page + /api/repos JSON endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_redirects_to_repos(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/repos"


def test_repos_page_renders_30_rows(client: TestClient) -> None:
    response = client.get("/repos")
    assert response.status_code == 200
    body = response.text
    assert "langchain" in body
    assert "vllm" in body
    assert body.count('data-repo-id="') == 30


def test_repos_api_returns_30(client: TestClient) -> None:
    response = client.get("/api/repos")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 30
    sample = payload[0]
    assert {"id", "org", "name", "full_name", "stars", "category"} <= set(sample.keys())


def test_repos_api_default_sort_is_stars_desc(client: TestClient) -> None:
    payload = client.get("/api/repos").json()
    stars = [row["stars"] for row in payload]
    assert stars == sorted(stars, reverse=True)


def test_repos_api_filter_by_category(client: TestClient) -> None:
    payload = client.get("/api/repos", params={"category": "Vector-DB"}).json()
    assert len(payload) >= 1
    assert all(row["category"] == "Vector-DB" for row in payload)


def test_repos_api_sort_by_forks_asc(client: TestClient) -> None:
    payload = client.get("/api/repos", params={"sort": "forks", "order": "asc"}).json()
    forks = [row["forks"] for row in payload]
    assert forks == sorted(forks)


def test_repos_api_sort_by_1d_delta(client: TestClient) -> None:
    payload = client.get("/api/repos", params={"sort": "stars_1d_delta", "order": "desc"}).json()
    deltas = [row["stars_1d_delta"] for row in payload]
    assert deltas == sorted(deltas, reverse=True)


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
