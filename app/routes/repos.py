"""``/repos`` page + ``/api/repos`` JSON endpoint."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Repo
from app.schemas import ReadRepo

router = APIRouter()

CATEGORIES: tuple[str, ...] = ("LLM", "Agents", "RAG", "Vector-DB", "Eval", "Tools")

SortKey = Literal[
    "stars",
    "stars_1d_delta",
    "stars_7d_delta",
    "forks",
    "name",
    "category",
    "created_at",
    "updated_at",
]
SortOrder = Literal["asc", "desc"]

_SORT_COLUMNS = {
    "stars": Repo.stars,
    "forks": Repo.forks,
    "name": Repo.name,
    "category": Repo.category,
    "created_at": Repo.created_at,
    "updated_at": Repo.updated_at,
}

_DELTA_KEYS: dict[str, str] = {
    "stars_1d_delta": "stars_1d_delta",
    "stars_7d_delta": "stars_7d_delta",
}


def query_repos(
    session: Session,
    *,
    category: str | None = None,
    sort: SortKey = "stars",
    order: SortOrder = "desc",
) -> list[Repo]:
    """Return repos filtered + sorted.

    Sort by computed delta columns is performed in Python because
    ``stars_1d_delta`` is a property (Phase B will materialise these
    on the row).
    """
    stmt = session.query(Repo)
    if category:
        stmt = stmt.filter(Repo.category == category)

    if sort in _SORT_COLUMNS:
        col = _SORT_COLUMNS[sort]
        stmt = stmt.order_by(desc(col) if order == "desc" else asc(col))
        return list(stmt.all())

    rows = list(stmt.all())
    if sort in _DELTA_KEYS:
        attr = _DELTA_KEYS[sort]
        rows.sort(key=lambda r: getattr(r, attr), reverse=(order == "desc"))
    return rows


def _make_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates  # type: ignore[no-any-return]


@router.get("/repos", response_class=HTMLResponse)
def repos_page(
    request: Request,
    category: str | None = Query(default=None),
    sort: SortKey = Query(default="stars"),
    order: SortOrder = Query(default="desc"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Render the repos table page."""
    rows = query_repos(session, category=category, sort=sort, order=order)
    templates = _make_templates(request)
    return templates.TemplateResponse(
        request,
        "repos.html",
        {
            "rows": rows,
            "categories": CATEGORIES,
            "selected_category": category or "",
            "sort": sort,
            "order": order,
        },
    )


@router.get("/api/repos", response_model=list[ReadRepo])
def repos_api(
    category: str | None = Query(default=None),
    sort: SortKey = Query(default="stars"),
    order: SortOrder = Query(default="desc"),
    session: Session = Depends(get_session),
) -> list[ReadRepo]:
    """JSON endpoint for the repos table — used by HTMX + tests."""
    rows = query_repos(session, category=category, sort=sort, order=order)
    return [ReadRepo.model_validate(r) for r in rows]
