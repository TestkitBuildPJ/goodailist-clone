# RUNBOOK

Operational quick reference for goodailist-clone Phase A.

## First-time setup

```bash
make install   # pip install -e ".[dev]"
make seed      # populate SQLite from seed_data/repos.json
```

## Daily dev loop

```bash
make run       # uvicorn on :8000
make test      # pytest
make check     # ruff + mypy --strict + coverage gate (mirror CI)
```

Endpoint sanity:

| Path | What |
|------|------|
| `/`              | 307 → `/repos` |
| `/repos`         | HTML table, filter+sort |
| `/charts`        | Chart.js cumulative line |
| `/api/repos`     | JSON, supports `?category=`, `?sort=`, `?order=` |
| `/api/charts/series` | JSON, list of `{category, points: [{date, stars}]}` |
| `/healthz`       | `{"status": "ok"}` |

## Resetting the database

```bash
rm -f goodailist.db
make seed
```

`reset_and_seed()` drops + recreates the `repos` table on every call so it's
idempotent — safe to run repeatedly.

## CI parity

The `make check` target runs the exact gates that `.github/workflows/ci.yml`
runs: `ruff check`, `mypy --strict`, `pytest`, `coverage report --fail-under=80`.
Run locally before pushing to avoid red CI.

## Pre-commit hook

```bash
pre-commit install
pre-commit run --all-files
```

Hook config at `.pre-commit-config.yaml` excludes `ai-rules/`, `.vibecode/`,
`.claw/` (vendored kit overlay).

## Phase B preview (NOT in this repo yet)

When we move to live ingest:

1. Add `app/ingest.py` calling GitHub REST API with conditional `If-None-Match`.
2. Add `repo_snapshots(repo_id, snapshot_date, stars, forks)` table.
3. Schedule `.github/workflows/ingest.yml` daily via `schedule: cron`.
4. `app/routes/charts.py` reads from `repo_snapshots` instead of approximating
   from anchor dates.
