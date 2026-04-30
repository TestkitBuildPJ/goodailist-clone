# SPEC — goodailist-clone Phase A MVP

> Source: https://goodailist.com/repos
> Methodology: VibecodeKit Hybrid Ultra v0.19.0 (overlay in `ai-rules/vibecodekit/`)

## Vision (1-line)

A static, locally-hosted clone of goodailist.com/repos that lists 30 curated AI-related GitHub repos, lets a developer filter by category and sort by any column, and visualises cumulative star growth per category — using only Python + a server-rendered HTMX page (no JS build step).

## Goals (Phase A)

| KPI | Target |
|-----|--------|
| Time to first useful page | < 1 second cold start |
| Tests | ≥ 10 backend tests, all green |
| Coverage on `app/` | ≥ 80 % branch coverage |
| Lines of TypeScript shipped | 0 (HTMX + Chart.js via CDN) |
| External network calls at runtime | 0 (seed JSON only) |

## Non-goals (Phase A)

- Live GitHub API ingest, daily cron refresh, ETag caching → Phase B.
- Drill-down by sub-category, country filter, developer/bot tables → Phase C.
- Auth, multi-user, RBAC.
- Production deploy, CDN, observability.

## Functional requirements

### `/repos`

1. Render an HTML table with columns: `#`, `Repo (org/name)`, `Stars`, `1d Δ`, `7d Δ`, `Forks`, `Description`, `Category`, `Created`, `Updated`.
2. Show all 30 seed repos by default.
3. `?category=<cat>` filters rows by category. The `<select>` triggers a form submit on change.
4. `?sort=<key>&order=<asc|desc>` controls sorting. Default = `sort=stars&order=desc`. Clicking a column header toggles asc/desc on that column.
5. Sort keys: `stars`, `stars_1d_delta`, `stars_7d_delta`, `forks`, `name`, `category`, `created_at`, `updated_at`.
6. JSON twin at `/api/repos` (used by tests).

### `/charts`

1. Render one Chart.js line chart `Cumulative Star Count Over Time`.
2. One series per category (`LLM`, `Agents`, `RAG`, `Vector-DB`, `Eval`, `Tools`).
3. Data source: per-repo anchor points `(created_at, 0)`, `(updated_at − 7d, stars_7d_ago)`, `(updated_at − 1d, stars_1d_ago)`, `(updated_at, stars)`, summed per category and made monotonically non-decreasing.
4. JSON twin at `/api/charts/series` (used by tests).

### Other endpoints

- `GET /` → 307 redirect to `/repos`.
- `GET /healthz` → `{ "status": "ok" }`.

## Data model

```python
class Repo(Base):
    __tablename__ = "repos"
    id: int                    # PK
    org: str                   # GitHub org/user, e.g. "langchain-ai"
    name: str                  # repo name
    stars: int                 # current count
    stars_1d_ago: int
    stars_7d_ago: int
    forks: int
    description: str
    category: Literal["LLM","Agents","RAG","Vector-DB","Eval","Tools"]
    created_at: date
    updated_at: date
    # computed properties: full_name, stars_1d_delta, stars_7d_delta
```

## Architecture (ASCII)

```
+-----------------------+      +----------------+      +-------------------+
|  Browser (HTMX)       | ---> | FastAPI app    | ---> | SQLite (file or   |
|  Tailwind + Chart.js  | <--- | Jinja2 + JSON  | <--- | in-memory)        |
|  CDN-only assets      |      | routers:       |      |  table: repos     |
+-----------------------+      |  /repos        |      +-------------------+
                               |  /charts       |             ^
                               |  /api/*        |             |
                               +----------------+             |
                                       |                      |
                                       v                      |
                                 app.seed.reset_and_seed -----+
                                       ^
                                       |
                                seed_data/repos.json (30 entries)
```

## Invariants

- I-1: `/api/repos` default ordering is `stars DESC`.
- I-2: `len(/api/repos) == 30` after seeding.
- I-3: For each chart series, points are sorted by date ASC and the cumulative
  star sequence is monotonically non-decreasing.
- I-4: Every `category` value present in the DB is one of the six canonical
  values OR is appended to the end of the chart series list (not enforced via
  CHECK constraint in Phase A — Phase B will add).
- I-5: `app.main.create_app()` is idempotent and safe to call from tests.

## Quality gates (Phase A release)

1. `pytest tests/ -q` → ≥ 10 passed, 0 failed.
2. `coverage report --fail-under=80` → green for `app/`.
3. `ruff check app/ tests/` → 0 errors.
4. `mypy --strict app/` → 0 errors.
5. CI workflow `.github/workflows/ci.yml` runs all four on every push.

## Phase A → B transition (out of scope this session)

- Replace `seed_data/repos.json` with a GitHub API ingest job (`app/ingest.py`).
- Add a `repo_snapshots(repo_id, snapshot_date, stars, forks)` table.
- Daily cron via GitHub Actions schedule writing snapshots → recompute charts.
- ETag + conditional fetch on the GitHub API.
