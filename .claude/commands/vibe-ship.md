---
description: Deploy to one of 7 targets (Vercel, Docker, VPS, Cloudflare, Railway, Fly, Render)
version: 0.11.2
allowed-tools: [Bash, Read]
deprecated: true
replaced-by: /vck-ship
removal-target: v1.0.0
deprecation-note: |
  /vck-ship hiện là canonical: bao trọn deploy + test → review → commit
  → push → PR (atomic, gate-driven), trong khi /vibe-ship chỉ lo
  deploy.  Giữ file này để backward-compat; các session cũ đang
  invoke /vibe-ship vẫn chạy. KHI bạn viết prompt mới, dùng
  /vck-ship.  Sẽ remove hẳn ở v1.0.0.
---

# /vibe-ship

The SHIP layer of VIBECODE-MASTER.  Auto-detects an appropriate
deploy target from the repo, runs preflight checks, executes the
deployment, and records state for rollback.

## Targets

| Driver | Detected via | Deploy command |
|---|---|---|
| `vercel`     | `vercel.json`, `next.config.*` | `npx vercel --prod` |
| `docker`     | `Dockerfile`, `compose.yaml`   | `docker build -t …`  (auto-generates Dockerfile if missing) |
| `vps`        | `.vps.env`                     | `rsync` + `ssh systemctl restart` |
| `cloudflare` | `wrangler.toml`                | `wrangler pages deploy` |
| `railway`    | `railway.json` / `.railway`    | `railway up --detach` |
| `fly`        | `fly.toml`                     | `flyctl deploy` |
| `render`     | `render.yaml`                  | `git push render main` (Render auto-deploys) |

## Usage

```bash
# Auto-detect target
python -m vibecodekit.cli ship

# Force a specific target
python -m vibecodekit.cli ship --target vercel --prod

# Dry-run (validate preflight, log commands without running)
python -m vibecodekit.cli ship --dry-run

# Show last deploy + history
python -m vibecodekit.cli ship history
python -m vibecodekit.cli ship rollback <snapshot_id>
```

## Programmatic API

```python
from vibecodekit.deploy_orchestrator import DeployOrchestrator, DryRunner

# Production (real shell)
o = DeployOrchestrator(repo_dir=".")
target = o.select_target()                # auto-detect
issues = target.preflight(o.repo)
result = o.run(target, opts={"prod": True})
print(result.url, result.snapshot_id)

# Tests / dry-run
o_dry = DeployOrchestrator(".", runner=DryRunner())
o_dry.run("docker", opts={"tag": "demo:1"})
```

## State files

After every deploy, the orchestrator writes:

- `.vibecode/deploy-target.txt`    — last target (e.g. `docker`)
- `.vibecode/deploy-url.txt`       — last public URL (when known)
- `.vibecode/deploy-history.jsonl` — append-only audit log

These files are git-friendly (text, append-only) and survive across
sessions, enabling `rollback(snapshot_id)` and `history()`.

## Preflight gates

Each driver runs preflight checks BEFORE attempting the deploy.
Examples:

- `VercelDriver`   → errors when `package.json` missing
- `VPSDriver`      → errors when `.vps.env` missing
- `FlyDriver`      → errors when `fly.toml` missing
- `DockerDriver`   → warns (not errors) when `Dockerfile` missing —
                     it auto-generates a starter Dockerfile

Errors abort the deploy; warnings are surfaced but don't block.

See `USAGE_GUIDE.md` §16.3 for the 7-driver table, auto-detect logic, history/rollback, and `DeployOrchestrator` Python API.
