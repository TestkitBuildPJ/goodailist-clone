# RUNBOOK — Phase B (live ingest)

Operational reference for goodailist-clone **Phase B** (snapshots + cron + admin endpoints + Fly.io deploy).
Phase A runbook in `/RUNBOOK.md` covers the dev-loop basics.

---

## TL;DR commands (assume Fly.io app `goodailist-clone-voutwdxm`)

```bash
# 0. set deploy URL secret on local box
export FLY_APP=goodailist-clone-voutwdxm

# 1. one-time: provision a 1 GB persistent volume in PRG region
fly volumes create goodailist_data --app $FLY_APP --region prg --size 1

# 2. one-time: stash GitHub PAT (fine-grained, public_repo:read) + admin token
fly secrets set GITHUB_TOKEN="$GITHUB_PAT" --app $FLY_APP
fly secrets set GOODAILIST_ADMIN_TOKEN="$(openssl rand -hex 32)" --app $FLY_APP

# 3. deploy
fly deploy --app $FLY_APP

# 4. smoke check
curl -fsS https://$FLY_APP.fly.dev/healthz
curl -fsS https://$FLY_APP.fly.dev/api/repos | jq '. | length'
curl -fsS https://$FLY_APP.fly.dev/api/charts/series | jq '. | length'
```

---

## 1. Persistent volume

Phase A used ephemeral SQLite (data wiped on every redeploy / restart). Phase B
must persist `goodailist.db` so cron-written snapshots survive across deploys.

### Provision once

```bash
fly volumes create goodailist_data \
  --app goodailist-clone-voutwdxm \
  --region prg \
  --size 1
```

### Mount in `fly.toml`

The deploy adapter auto-generates `fly.toml`. After the first `fly deploy`,
edit it to add a `[mounts]` section:

```toml
[mounts]
  source = "goodailist_data"
  destination = "/data"
```

Then point the app at the mounted path via env:

```bash
fly secrets set GOODAILIST_DB_URL="sqlite:////data/goodailist.db" --app $FLY_APP
fly deploy --app $FLY_APP
```

(Note 4 slashes — `sqlite:///` + absolute path `/data/goodailist.db`.)

### Verify mount

```bash
fly ssh console --app $FLY_APP --command "ls -la /data"
fly ssh console --app $FLY_APP --command "stat /data/goodailist.db"
```

---

## 2. Secrets

Phase B needs **two** secrets:

| Name | Purpose | Format |
|------|---------|--------|
| `GITHUB_TOKEN` | Authenticates GitHub REST calls (5k req/h). | Fine-grained PAT, scope `public_repo: read`. |
| `GOODAILIST_ADMIN_TOKEN` | Gates `/admin/refresh` + `/admin/runs`. | Random hex, ≥32 chars. |

```bash
# Generate the admin token client-side (don't echo to logs).
ADMIN=$(openssl rand -hex 32)
fly secrets set GOODAILIST_ADMIN_TOKEN="$ADMIN" --app $FLY_APP
echo "$ADMIN" > ~/.goodailist-admin-token  # keep locally, NEVER commit
chmod 600 ~/.goodailist-admin-token

# GitHub PAT — create at https://github.com/settings/personal-access-tokens
fly secrets set GITHUB_TOKEN="github_pat_xxx" --app $FLY_APP
```

### Rotation

Both secrets are read by the scheduler on **every cron iteration**, not at
boot, so rotation does not require a redeploy:

```bash
fly secrets set GITHUB_TOKEN="github_pat_NEW" --app $FLY_APP
# next cron tick (≤ 24h) will use the new token; force-refresh now via:
curl -fsS -X POST https://$FLY_APP.fly.dev/admin/refresh \
  -H "X-Admin-Token: $(cat ~/.goodailist-admin-token)"
```

---

## 3. Schema migration

Schema lives in `alembic/versions/`. Migrations are applied automatically at
container startup via `app.db.init_db()` + `app.seed.backfill_anchors_into()`,
so a fresh deploy on an empty volume bootstraps to a working state.

### Manual migration (only if you bypass startup)

```bash
fly ssh console --app $FLY_APP \
  --command "cd /app && alembic upgrade head"
```

### Rollback

```bash
fly ssh console --app $FLY_APP \
  --command "cd /app && alembic downgrade -1"
```

The Phase B `0003_phase_b_backfill` downgrade preserves real cron-written
snapshots (filters on `(captured_at, forks)` so rows whose forks don't match
the synthesised baseline survive — see `alembic/versions/0003_phase_b_backfill.py`).

---

## 4. Admin endpoints

`POST /admin/refresh` — manual trigger of the cron iteration.
`GET  /admin/runs?limit=N` — list latest `ingest_run` rows.

Both require `X-Admin-Token: <secret>` header; missing/wrong returns 401.

```bash
TOKEN=$(cat ~/.goodailist-admin-token)

curl -fsS -X POST https://$FLY_APP.fly.dev/admin/refresh \
  -H "X-Admin-Token: $TOKEN" | jq

curl -fsS "https://$FLY_APP.fly.dev/admin/runs?limit=5" \
  -H "X-Admin-Token: $TOKEN" | jq
```

---

## 5. Cron schedule

APScheduler runs in-process inside the FastAPI app (`app/ingest/scheduler.py`).

| Setting | Value | Where |
|---------|-------|-------|
| Cron expr | `0 3 * * *` (03:00 UTC daily) | `scheduler.py` |
| `coalesce` | `True` (skip backlog after restart) | `scheduler.py` |
| `max_instances` | `1` (no overlap) | `scheduler.py` |

Disabled when `GITHUB_TOKEN` is unset (CI / dev). Logs show
`"ingest scheduler dormant — GITHUB_TOKEN not set"` in that mode.

---

## 6. Monitoring queries

The footer on `/repos` and `/charts` shows freshness + a stale banner above
the page when last snapshot is > 24 h old (TIP-B07).

For deeper visibility:

```bash
# Latest 5 ingest runs + their status.
fly ssh console --app $FLY_APP \
  --command "sqlite3 /data/goodailist.db 'SELECT started_at, finished_at, status, repos_updated, etag_hits FROM ingest_runs ORDER BY id DESC LIMIT 5;'"

# Snapshot count + max(captured_at).
fly ssh console --app $FLY_APP \
  --command "sqlite3 /data/goodailist.db 'SELECT COUNT(*), MAX(captured_at) FROM repo_star_snapshots;'"

# ETag hit rate over the last 7 days (target ≥ 50%).
fly ssh console --app $FLY_APP \
  --command "sqlite3 /data/goodailist.db \"SELECT SUM(etag_hits) * 100.0 / SUM(repos_updated) FROM ingest_runs WHERE started_at > datetime('now', '-7 days');\""
```

---

## 7. Troubleshooting

### Banner shows "data may be stale"

1. Check most recent `ingest_runs` row — was the last cron tick `success` or `failed`?
2. If `failed`: tail logs `fly logs --app $FLY_APP` for the traceback.
3. If GitHub returned 401: rotate `GITHUB_TOKEN`.
4. Manual recovery: `POST /admin/refresh` with the admin token (see §4).

### `/repos` and `/charts` 500

Most often a stale schema after a botched migration. Verify:

```bash
fly ssh console --app $FLY_APP \
  --command "sqlite3 /data/goodailist.db '.schema repo_star_snapshots'"
```

If empty, run `alembic upgrade head` (§3).

### Volume disk full

```bash
fly ssh console --app $FLY_APP --command "df -h /data"
fly volumes extend <volume_id> --size 5  # bump to 5 GB
```

---

## 8. Deploy through Devin (current setup)

Phase B is currently shipped via `deploy backend` (Devin's Fly.io adapter), not
manual `fly deploy`.  The adapter:

1. Generates `Dockerfile` + `fly.toml` from `pyproject.toml`.
2. Sets `PORT` + invokes `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Uploads to Fly.io as the same app slug across redeploys.

To attach a persistent volume through that adapter, pass `volume=true` to the
`deploy backend` call. The volume mount is at `/data` and the app reads it
through `GOODAILIST_DB_URL=sqlite:////data/goodailist.db`.

Without the volume flag, every redeploy re-seeds + re-runs `backfill_anchors_into`
on a fresh empty SQLite — the Phase A anchor approximation still renders the
chart, but real cron-written snapshots are lost.
