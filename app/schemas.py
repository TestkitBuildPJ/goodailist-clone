"""Pydantic response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ReadRepo(BaseModel):
    """Public read model for a repository row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org: str
    name: str
    full_name: str
    stars: int
    stars_1d_delta: int
    stars_7d_delta: int
    forks: int
    description: str
    category: str
    created_at: date
    updated_at: date


class ChartPoint(BaseModel):
    """One (date, cumulative_stars) point in a category series."""

    date: date
    stars: int


class ChartSeries(BaseModel):
    """One named series for the cumulative-star chart."""

    category: str
    points: list[ChartPoint]


class IngestRunRead(BaseModel):
    """Audit row for one ingest run, surfaced via ``/admin/runs``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    repos_updated: int
    api_calls: int
    etag_hits: int
    error_msg: str | None


class RefreshResponse(BaseModel):
    """Response payload for ``POST /admin/refresh``."""

    run_id: int | None
    status: str
    repos_updated: int
    api_calls: int
    etag_hits: int
    error_msg: str | None
