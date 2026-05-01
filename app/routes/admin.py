"""Admin endpoints — manual refresh + run history.

All routes require ``X-Admin-Token`` header matching ``ADMIN_TOKEN`` env.
When ``ADMIN_TOKEN`` is unset, every request is denied (fail-closed).
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import get_engine, get_session
from app.ingest import scheduler as scheduler_module
from app.ingest.ingestor import run_once
from app.models import IngestRun
from app.schemas import IngestRunRead, RefreshResponse

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Dependency: deny unless ``X-Admin-Token`` matches ``ADMIN_TOKEN`` env.

    Fails closed if ``ADMIN_TOKEN`` is unset (no anonymous access ever).
    """
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or x_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing X-Admin-Token",
        )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    dependencies=[Depends(require_admin_token)],
)
async def refresh_now(
    engine: Engine = Depends(get_engine),
) -> RefreshResponse:
    """Trigger one ingest tick synchronously.  Returns the resulting stats."""
    stats = await run_once(engine=engine, store=scheduler_module.ETAG_STORE)
    return RefreshResponse(
        run_id=stats.run_id,
        status=stats.status,
        repos_updated=stats.repos_updated,
        api_calls=stats.api_calls,
        etag_hits=stats.etag_hits,
        error_msg=stats.error_msg,
    )


@router.get(
    "/runs",
    response_model=list[IngestRunRead],
    dependencies=[Depends(require_admin_token)],
)
def list_runs(
    limit: int = 20,
    session: Session = Depends(get_session),
) -> list[IngestRunRead]:
    """Return the most recent ingest runs, newest first."""
    capped = max(1, min(limit, 200))
    rows = session.query(IngestRun).order_by(IngestRun.id.desc()).limit(capped).all()
    return [IngestRunRead.model_validate(row, from_attributes=True) for row in rows]
