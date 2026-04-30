---
description: Scaffold a runnable starter project from a preset (9 presets × 3 stacks)
version: 0.11.3
allowed-tools: [Bash, Read, Write]
wired_refs: [ref-34]
agent: builder
---

# /vibe-scaffold

Generate a runnable starter project in seconds — pick a preset and a
stack and the engine writes the file tree.  All 9 bundled presets:

| Preset | Stacks | What it builds |
|---|---|---|
| `landing-page` | nextjs | Marketing landing + email capture |
| `shop-online`  | nextjs | Product catalog + cart skeleton |
| `crm`          | nextjs **\|** fastapi | Contacts CRUD (web or API) |
| `blog`         | nextjs | MDX blog with listing |
| `dashboard`    | nextjs | KPI cards + recharts |
| `api-todo`     | fastapi | REST todo + pytest |
| `mobile-app`   | expo   | Expo React Native starter |
| `portfolio`    | nextjs | Hero + Work + Contact (Framer Motion, Pattern E) |
| `saas`         | nextjs | NextAuth + Prisma + auth/dashboard split (Pattern B) |

Each preset declares `success_criteria` that `verify()` runs — the
engine will tell you immediately if the scaffold drifted.

## Usage

```bash
# List all available presets
python -m vibecodekit.cli scaffold list

# Preview file tree (dry-run)
python -m vibecodekit.cli scaffold preview landing-page --stack nextjs

# Apply scaffold to ./my-site
python -m vibecodekit.cli scaffold apply landing-page ./my-site --stack nextjs

# Verify (run preset success criteria)
python -m vibecodekit.cli scaffold verify ./my-site
```

## Programmatic API

```python
from vibecodekit.scaffold_engine import ScaffoldEngine
engine = ScaffoldEngine()
plan = engine.preview("crm", stack="fastapi", target_dir="./crm-api")
result = engine.apply("crm", "./crm-api", stack="fastapi")
issues = engine.verify(result)
assert not issues, issues
```

## Multi-stack support

Some presets ship multiple stack variants — `crm` for instance has both
`nextjs` (web UI) and `fastapi` (REST API).  Combine them by scaffolding
both into a monorepo:

```bash
python -m vibecodekit.cli scaffold apply crm ./crm/web --stack nextjs
python -m vibecodekit.cli scaffold apply crm ./crm/api --stack fastapi
```

See `USAGE_GUIDE.md` §16.2 for the 9-preset table, multi-stack monorepo, and `ScaffoldEngine` Python API.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-scaffold \
  --project-type <type>
```

**Wired references:** ref-34 — loaded verbatim by `methodology.render_command_context`.

**Dynamic data sources:** recommend_stack — pulled at runtime per project context.

**Default agent:** `builder` (auto-spawned via `subagent_runtime.spawn_for_command`).  Override per command by editing the `agent:` frontmatter field.

<!-- v0.11.3-runtime-wiring-end -->
