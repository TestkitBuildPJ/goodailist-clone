# goodailist-clone (Phase A MVP)

Clone của [goodailist.com/repos](https://goodailist.com/repos) — dashboard liệt kê AI-related GitHub repos với chart cumulative star theo thời gian. Build sử dụng **VibecodeKit Hybrid Ultra v0.19.0** làm rule overlay.

## Phase A scope

- Trang `/repos`: bảng 30 seed repos với cột `#`, `Repo`, `Stars`, `1d Δ`, `7d Δ`, `Forks`, `Description`, `Category`, `Created`, `Updated`. Filter category + sort theo column.
- Trang `/charts`: line chart "Cumulative Star Count Over Time" multi-series theo category.
- Backend: **FastAPI 0.115 + SQLAlchemy 2.0 + SQLite**.
- Frontend: **HTMX + Tailwind (CDN) + Chart.js (CDN)**, server-side render Jinja2 — không build step.
- Tests: pytest ≥10 tests, coverage ≥80% cho `app/`.
- CI: GitHub Actions chạy `ruff` + `mypy --strict` + `pytest` + `coverage`.

Phase B (live GitHub ingest, cron) và Phase C (drill-down, dev table, deploy production) **out-of-scope** session này.

## Run local

```bash
python3 -m pip install -e ".[dev]"
python3 -m app.seed                       # load seed_data/repos.json -> SQLite
uvicorn app.main:app --reload
# Open http://localhost:8000/repos
# Open http://localhost:8000/charts
```

## Testing

```bash
python3 -m pytest tests/ -v
python3 -m coverage run --source=app -m pytest tests/
python3 -m coverage report --fail-under=80
python3 -m ruff check app/ tests/
python3 -m mypy --strict app/
```

## Project layout

```
app/
├── main.py          # FastAPI app + Jinja2 setup
├── db.py            # engine + SessionLocal + Base
├── models.py        # SQLAlchemy Repo model
├── schemas.py       # Pydantic ReadRepo
├── seed.py          # seed_data/repos.json -> DB loader
├── routes/
│   ├── repos.py     # GET /repos, GET /api/repos
│   └── charts.py    # GET /charts, GET /api/charts/series
├── templates/       # base.html, repos.html, charts.html
└── static/          # (CDN-only for now)
seed_data/
└── repos.json       # 30 curated AI repos
tests/
├── conftest.py      # fresh in-memory DB per test
├── test_seed.py
├── test_repos_endpoint.py
├── test_charts_endpoint.py
└── test_models.py
```

## Kit overlay

VibecodeKit rules + slash commands ship trong `ai-rules/vibecodekit/`, `.claude/`, `.claw/`. AGENTS.md ở repo root là CLAUDE overlay từ kit.
