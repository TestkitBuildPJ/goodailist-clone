# Project overlay — VibecodeKit Hybrid Ultra v0.18.0

This project uses the VibecodeKit **v0.18.0** overlay (canonical version
file: `VERSION`).  All tool calls pass through the 6-layer permission
pipeline; see
`ai-rules/vibecodekit/references/10-permission-classification.md`.

## Quick commands (42 slash commands total — 25 `/vibe-*` + 1 master `/vibe` + 16 `/vck-*`)

The canonical inventory lives in `manifest.llm.json`; this file lists
the most-used subset for context.

### Lifecycle
- `/vibe-scan`         — scan repo + docs (step 1)
- `/vibe-rri`          — Reverse Requirements Interview, 5 personas
- `/vibe-vision`       — define goals, KPIs, non-goals
- `/vibe-blueprint`    — architecture + data model + interfaces
- `/vibe-tip`          — Task Instruction Pack
- `/vibe-task`         — DAG + agent/workflow/monitor/dream tasks
- `/vibe-subagent`     — spawn agent (coordinator/scout/builder/qa/security)
- `/vibe-run <plan>`   — execute query-loop plan
- `/vibe-verify`       — adversarial QA gate
- `/vibe-complete`     — completion report
- `/vibe-refine`       — refine ticket (BƯỚC 8/8) + boundary classifier
- `/vibe-module`       — Pattern F: add module to existing codebase (reuse-max/build-min)

### Quality gates
- `/vibe-rri-t <jsonl>`   — testing release gate (7 dims × 8 axes)
- `/vibe-rri-ux <jsonl>`  — UX release gate (7 dims × 8 Flow Physics axes)
- `/vibe-rri-ui`          — UI design pipeline (DISCOVER→CRITIQUE→ITERATE→HARDEN)

### Runtime
- `/vibe-memory`       — memory hierarchy (user/project/team)
- `/vibe-approval`     — human-in-the-loop approval JSON contract
- `/vibe-permission <cmd>` — dry-run a command through permission pipeline
- `/vibe-compact [--reactive]` — 5-layer compaction
- `/vibe-doctor`       — health check
- `/vibe-dashboard`    — runtime event summary
- `/vibe-audit`        — 87-probe internal conformance self-test ([methodology](BENCHMARKS-METHODOLOGY.md))
- `/vibe-install <dst>` — install overlay into another project

CLI-only commands (no slash form):
- `vibe mcp {list,register,call,tools,disable}` — MCP server management
- `vibe ledger {summary,reset}` — token/cost ledger
- `vibe vn-check --file <flags.json>` — Vietnamese 12-point checklist
- `vibe config {show,set-backend,get}` — embedding backend persistence
- `vibe rri-t <jsonl>` / `vibe rri-ux <jsonl>` — methodology runners
- `vibe discover` — dynamic skill discovery

## Methodology (8 steps)

1. **Scan** (`/vibe-scan`) — read-only scout pass over repo + docs.
2. **RRI** (`/vibe-rri [CHALLENGE|GUIDED|EXPLORE]`) — 5 personas reverse-interview.
3. **Vision** (`/vibe-vision`) — pin 1-line goal + 3 KPIs + non-goals.
4. **Blueprint** (`/vibe-blueprint`) — architecture + data + interface.
5. **Task graph** (`/vibe-task graph`) — DAG of TIPs.
6. **Build** (`/vibe-subagent builder …`) — one TIP per builder.
7. **Verify** — run `/vibe-rri-t`, `/vibe-rri-ux`, `/vibe-vn-check` gates.
8. **Release** — `/vibe-complete` + `/vibe-audit` → ship.

## Sub-agent ACL (7 roles)

| Role        | Read | Write | Run shell | Push | Notes |
|-------------|:---:|:-----:|:---------:|:----:|-------|
| coordinator | ✓   | ✗     | ✗         | ✗    | planning + task-control + approvals |
| scout       | ✓   | ✗     | ✓ (read)  | ✗    | grep/glob/read |
| builder     | ✓   | ✓     | ✓         | ✗    | implementation; high-risk bubble-escalates |
| qa          | ✓   | ✗     | ✓         | ✗    | run tests / verification only |
| security    | ✓   | ✗     | ✓ (read)  | ✗    | OWASP / STRIDE audit; redacts logs |
| reviewer    | ✓   | ✗     | ✓ (read)  | ✗    | adversarial 7-specialist review |
| qa-lead     | ✓   | ✗     | ✓ (read)  | ✗    | real-browser checklist + fix-loop proposals |

Enforced by `scripts/vibecodekit/subagent_runtime.py` (`PROFILES`);
coordinator / scout / qa / security / reviewer / qa-lead physically
cannot write files (`can_mutate=False`).

## Hook events (33 lifecycle points)

Events in `hook_interceptor.SUPPORTED_EVENTS` span 9 groups:
Tool (3) · Permission (2) · Session (3) · Agent (3) · Task (4) ·
Context (3) · Filesystem (4) · UI/Config (5) · Query legacy (6).

Hooks in `.claw/hooks/`:
- `pre_tool_use.py`     — block 40+ dangerous patterns
- `post_tool_use.py`    — log + redact secrets
- `pre_compact.py`      — pre layer-4/5 compaction
- `session_start.py`    — init runtime

## Memory hierarchy (3 tiers)

- **user**    — `~/.vibecode/memory/`             (cross-project)
- **project** — `.vibecode/memory/`               (repo-local)
- **team**    — `.vibecode/memory/team/`          (commit to repo)

Retrieval: hybrid lexical + embedding (default backend: `hash-256`,
offline; override via `vibe config set-backend sentence-transformers`).

## Approval JSON contract

All risky actions (diff, permission escalation, elicitation) go through
`approval_contract.create(…)` which writes a JSON file and returns
`appr-<16hex>`.  Choices default to `{allow, deny}`; override via API.

## Vietnamese 12-point checklist

When scope covers VN users, run `vibe vn-check --file flags.json`.
Gate FAILs on any missing key.  Canonical keys in
`references/32-rri-ux-critique.md §9`.

## MCP (Model Context Protocol)

- `vibe mcp register <name> --transport stdio --command <argv> --handshake`
  — full initialize + tools/list + tools/call handshake
- `vibe mcp register <name> --transport inproc --module <dotted>`
  — in-process Python MCP server

Bundled sample server: `python -m vibecodekit.mcp_servers.selfcheck`
(tools: `ping`, `echo`, `now`).

## Version — single source of truth

Only `VERSION` (repo root) is authoritative.  All other surfaces are
mirrors validated by `tests/test_docs_count_sync.py`.  Bumping version:

```bash
echo "0.17.0" > VERSION
python tools/sync_version.py          # writes to all 7 mirror surfaces
pytest tests/test_docs_count_sync.py  # verify mirrors agree
```

Mirror surfaces: `update-package/VERSION`, `pyproject.toml`,
`manifest.llm.json`, `assets/plugin-manifest.json`,
`update-package/.claw.json`, `SKILL.md` frontmatter,
`update-package/.claude/commands/vck-pipeline.md` frontmatter.

## Release gate

Before shipping:
1. `pytest tests/ -q` → 588/588 pass at v0.18.0 (full suite, run từ repo
   root; the canonical count is whatever `pytest --collect-only -q | tail`
   reports for the current commit).  Bundled `tests/` trong zip chỉ là
   subset đại diện; đủ để smoke-test sau khi unzip nhưng CI gate là trên
   full suite.
2. `/vibe-audit` → 87/87 internal regression probes (self-test, not external benchmark)
3. `/vibe-rri-t` → all 7 dims ≥ 70 %, ≥ 5/7 @ ≥ 85 %, 0 P0 FAIL
4. `/vibe-rri-ux` → same structure on Flow Physics
5. `/vibe-vn-check` → gate PASS (12/12) if VN scope
6. `/vibe-complete` → final report signed off
