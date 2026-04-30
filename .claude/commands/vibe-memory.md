---
description: Query the 3-tier memory hierarchy + auto-maintain CLAUDE.md
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-memory

Two complementary capabilities:

1. **3-tier memory retrieval** (User / Project / Team) — Giải phẫu Ch 11.
2. **CLAUDE.md auto-maintain** (new in v0.10.8 — F6) — keeps the repo's
   `CLAUDE.md` in sync with detected stack, scripts, conventions,
   gotchas, and test strategy via `<!-- vibecode:auto:* -->` markers.

## 3-tier memory retrieval

```bash
# Retrieve by query (lexical + embedding hybrid, top 8 by default)
python -m vibecodekit.cli memory retrieve "lint rules"

# Add a new entry to project memory
python -m vibecodekit.cli memory add project "Use ruff 0.4 with config in pyproject.toml"

# Show entry counts per tier
python -m vibecodekit.cli memory stats
```

Project memory beats Team; Team beats User on exact matches.  Queries are
diacritic-insensitive, so "du an" matches "dự án".

Tiers:
- **user**   — `$VIBECODE_USER_MEMORY` (default: `~/.vibecode/memory`)
- **team**   — `$VIBECODE_TEAM_DIR/memory`
- **project**— `.vibecode/memory/` inside the repo

## CLAUDE.md auto-maintain (writeback)

```bash
# First-time scaffold — generates CLAUDE.md from detected repo state
python -m vibecodekit.cli memory writeback init

# Refresh auto sections (preserves user content outside markers)
python -m vibecodekit.cli memory writeback update

# Drift report — what's stale, missing, or extra
python -m vibecodekit.cli memory writeback check

# Nested CLAUDE.md for a sub-package
python -m vibecodekit.cli memory writeback nest apps/api

# Preview without writing
python -m vibecodekit.cli memory writeback update --dry-run
```

Auto-maintained sections:
- **stack** — Next.js / FastAPI / React / Expo / Python / Node / Go / Rust
- **scripts** — `package.json` scripts + `Makefile` targets
- **conventions** — `src/api/`, `app/main.py`, `components/`, `tests/` etc.
- **gotchas** — top recurring errors from `.vibecode/run-history.jsonl`
- **test-strategy** — pytest / vitest / jest detected commands

User content **outside** `<!-- vibecode:auto:*:begin -->` … `:end -->`
markers is preserved byte-for-byte.  See
`USAGE_GUIDE.md` §16.4 for marker semantics, dry-run, drift detection, and `MemoryWriteback` Python API.

See `ai-rules/vibecodekit/SKILL.md` for embedding-backend configuration.

## References

- `ai-rules/vibecodekit/references/24-memory-governance.md`
