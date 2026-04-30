---
name: vibecodekit-hybrid-ultra
version: 0.19.0
description: >-
  Full Agentic-OS overlay for Claude Code / Devin / Cursor projects with
  the VIBECODE-MASTER methodology layer on top.  Verified by an internal
  conformance self-test (53 runtime probes: 3-tier memory,
  approval / elicitation contract, all 7 task kinds, 4-phase DreamTask,
  MCP stdio, 26 hook events, cost ledger, fcntl-locked denial store,
  follow-up re-execute) and adds methodology probes: RRI (Reverse
  Requirements Interview, 5 personas × 3 modes), RRI-T (5 testing
  personas × 7 dimensions × 8 stress axes), RRI-UX (5 UX personas × 7
  dimensions × 8 flow physics axes), RRI-UI (four-phase design pipeline
  combining RRI-UX + RRI-T), VIBECODE-MASTER (3-actor, 8-step
  workflow SCAN → RRI → VISION → BLUEPRINT → TASK GRAPH → BUILD →
  VERIFY → REFINE), plus the BIG-UPDATE layer (xem `CHANGELOG.md` cho lineage chi tiết): F1 scaffold
  engine (10 preset × 3 stacks: Next.js / FastAPI / Expo), F2 deploy
  orchestrator (7 target: Vercel / Docker / VPS / Cloudflare / Railway
  / Fly / Render), F3 auto-commit hook + sensitive-file pre-write
  guard, F4 single-prompt /vibe router (14 tier-1 intents, VN+EN), F5
  VN error translator + VN faker, F6 CLAUDE.md auto-maintain (5
  sections).  Ships on top of v0.7.1's 18 Claude-Code runtime patterns
  and v0.10.x security hardening (11+3 permission bypass classes
  closed, Unicode normalisation, sensitive-file guard).
when_to_use: >-
  Activate at the start of any non-trivial engineering session: system design,
  multi-file refactor, cross-repo migration, regulated/SOC-sensitive work,
  background-task orchestration, long-running builds with incremental output,
  or any task where tool-permission hygiene, recovery, cost observability, and
  verifiable conformance matter more than raw speed.
triggers:
  - /vibe-run
  - /vibe-doctor
  - /vibe-dashboard
  - /vibe-audit
  - /vibe-permission
  - /vibe-install
  - /vibe-subagent
  - /vibe-compact
  - /vibe-blueprint
  - /vibe-tip
  - /vibe-verify
  - /vibe-complete
  - /vibe-task
  - /vibe-mcp
  - /vibe-ledger
  - /vibe-memory
  - /vibe-approval
  - /vibe-scan
  - /vibe-vision
  - /vibe-rri
  - /vibe-rri-t
  - /vibe-rri-ux
  - /vibe-rri-ui
  - /vck-cso
  - /vck-review
  - /vck-qa
  - /vck-qa-only
  - /vck-ship
  - /vck-investigate
  - /vck-canary
  - /vck-office-hours
  - /vck-ceo-review
  - /vck-eng-review
  - /vck-design-consultation
  - /vck-design-review
  - /vck-learn
  - /vck-retro
  - /vck-second-opinion
  - /vck-pipeline
paths:
  - "**/.vibecode/**"
  - "**/.claw/**"
  - "**/.claw.json"
  - "**/SKILL.md"
  - "**/CLAUDE.md"
  - "**/manifest.llm.json"
  - "**/ai-rules/vibecodekit/**"
  - "**/scripts/vibecodekit/**"
  - "**/assets/plugin-manifest.json"
  - "**/assets/scaffolds/**"
  - "**/assets/templates/**"
  - "**/pyproject.toml"
  - "**/.claude/commands/**"
  - "**/.claude/agents/**"
  - "**/references/**"
  - "**/tools/**"
requires:
  python: ">=3.9"
  git: ">=2.20"
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, Agent, WebFetch]
context: inline
effort: high
hooks:
  PreToolUse:
    - match_tool: "*"
      command: "python3 -m vibecodekit.cli permission ${command}"
  PreCompact:
    - match_tool: "*"
      command: "python3 -m vibecodekit.cli compact"
---

# VibecodeKit Hybrid Ultra — current: see [`VERSION`](VERSION) (at current main; xem [`CHANGELOG.md`](CHANGELOG.md))

For the canonical version history see `CHANGELOG.md`; the per-version
sections below document **how the kit evolved** — each subsection
describes when a subsystem was originally introduced, not the version
it currently runs.

## v0.11.4.1 patch — root-safe tests + canonical gate (historical)

Test-harness and release-gate polish only; runtime bit-identical to
v0.11.4.  Canonical release gate moving forward is:

1. `python -m pytest tests -q`
2. `python tools/validate_release_matrix.py --skill X --update Y`

Reviewers should run `pytest` directly; `--with-pytest` on the matrix
script is optional / non-canonical and may hang in constrained CI
environments.  See CHANGELOG.

## v0.11.4 polish (P3-1..3 + Obs-1/2 from stress-dipdive)

Defensive hardening; no feature or runtime-architecture change.

* **P3-1 — install concurrency lock**: `install_manifest.install()` now
  takes an advisory `fcntl` lock on `<dst>/.vibecode/runtime/install.lock`
  before planning+applying.  Two concurrent `install` calls against the
  same destination serialise cleanly instead of both doing full 251-file
  copies in parallel; the second caller sees an already-committed
  filesystem and reports 251 idempotent skips.
* **P3-2 — CLI error hygiene**: `_cmd_install` and `_cmd_scaffold` wrap
  `PermissionError` / `FileExistsError` / `IsADirectoryError` /
  `NotADirectoryError` / generic `OSError` / `ValueError` into a
  single-line JSON diagnostic on stderr and `exit 1`, instead of
  emitting a raw Python traceback.
* **P3-3 — Cf-category Unicode strip**: `permission_engine._normalise_unicode`
  now strips all `Cf`-category codepoints (ZWS / ZWNJ / ZWJ / BOM /
  WORD JOINER / SOFT HYPHEN) before regex matching.  `rm\u200b -rf /`
  now classifies as `blocked` instead of slipping to `mutation`.
* **Obs-1 — question-bank depth for api-todo / crm / mobile-app**:
  `assets/rri-question-bank.json` gains three dedicated buckets (`api`,
  `crm`, `mobile`) with 30 questions each (balanced over 5 personas × 3
  modes), and aliases `api-todo → api`, `mobile-app → mobile`,
  `crm → crm` (plus `rest-api`, `backend`, `expo`, `react-native`, `rn`).
  Previously these presets fell back to the 16-question `custom` bank.
* **Obs-2 — VN posture docs**: `load_rri_questions` docstring now
  documents explicitly that the RRI methodology is prompt-language-
  agnostic (personas / modes / IDs are structural and locale-free)
  while the shipped `q` text is Vietnamese-first for the VIBECODE-MASTER
  target audience.  LLM hosts translate on render as needed.

## v0.11.3 wiring patch (A + B + C)

Closes the structural wiring gaps surfaced by the v0.11.2 deep-dive:

* **Patch A — references → prompts**: `methodology.load_reference()` /
  `load_reference_section()` / `render_command_context()` compose ref bodies
  + dynamic data (`recommend_stack`, `load_rri_questions`) into a single
  prompt block per slash command.  Wiring map covers `vibe-vision`,
  `vibe-rri`, `vibe-rri-ui`, `vibe-rri-ux`, `vibe-rri-t`, `vibe-blueprint`,
  `vibe-verify`, `vibe-refine`, `vibe-audit`, `vibe-module`, `vibe-scaffold`.
  New CLI: `vibe context --command <name> [--project-type --persona --mode-filter]`.
* **Patch B — agent auto-spawn**: `subagent_runtime.spawn_for_command()`
  resolves a slash command to its default role (`coordinator` / `builder` /
  `qa` / `security` / `scout`) with frontmatter override.  Six commands ship
  with explicit `agent:` fields.
* **Patch C — paths-based lazy-load**: `skill_discovery.activate_for(path)`
  walks SKILL.md `paths:` globs (`**/*.py`, `**/*.tsx`, …) and reports
  whether the v0.11.x skill should activate.  `pre_tool_use` hook emits an
  advisory `skill_activation` signal so hosts (Claude Code / Devin / Cursor)
  can lazy-load the skill on first matching tool call.  New CLI:
  `vibe activate <path>`.
* Conformance audit: **53/53 PASS** at 100 % threshold (probes #51/#52/#53
  added).  Pytest: all actionable tests pass (32 new tests for A/B/C in
  v0.11.3, plus docs-count guards added in v0.11.3.1).

## v0.11.2 content depth (Builder TIP-FIX-001..007 — historical)

* **Docs scaffold preset** (Pattern D, Nextra-based) wired into
  `/vibe-build` via `intent_router` (`docs`, `tài liệu`,
  `documentation` → BUILD).  See `assets/scaffolds/docs/`.
* **Stack recommendations**: `methodology.recommend_stack(project_type)`
  covers 11 canonical types (`landing` / `saas` / `dashboard` / `blog` /
  `docs` / `portfolio` / `ecommerce` / `mobile` / `api` /
  `enterprise-module` / `custom`).  Vision template is pre-filled.
* **RRI question bank**: `assets/rri-question-bank.json` v1.1.0 — 293
  questions across 9 project types, 5 personas
  (`end_user`/`ba`/`qa`/`developer`/`operator`), 3 modes
  (`CHALLENGE`/`GUIDED`/`EXPLORE`).  `methodology.load_rri_questions(
  project_type, persona=None, mode=None)` with safe fallback to `custom`.
* **Style tokens (FP / CP / VN typography)**: `references/34-style-tokens.md`
  now ships VN-01..VN-12 typography rules (line-height, font subsets,
  layout) on top of the existing FP-01..FP-06 / CP-01..CP-06 rosters.
* **Copy patterns (split out)**: `references/36-copy-patterns.md` — new
  CF-01..CF-09 (headlines, CTA, social-proof, **pricing**, **empty
  state**, **error state**) plus 8 Vietnamese copy rules CF-VN-01..08.
  Exposed via `methodology.COPY_PATTERNS` (9) + `COPY_PATTERNS_VN` (8).
* Conformance audit at that time expanded to **50 probes** at 100 %
  threshold (probes #48/#49/#50 added).  Current release runs the
  87-probe internal self-test — see `CHANGELOG.md` for the per-version
  delta and `BENCHMARKS-METHODOLOGY.md` for what the self-test measures
  (and does not measure).

> 📌 The table and prose below describe **how the kit evolved** — each row
> lists the version a subsystem was *originally introduced*, not the version
> it currently runs.  The shipping runtime is whatever [`VERSION`](VERSION) reports at current main (xem [`CHANGELOG.md`](CHANGELOG.md)); every subsystem
> below is active, hardened, and covered by the 87-probe internal
> conformance self-test plus supporting tests (note: this is an internal
> regression guard, not an external quality benchmark — see
> [`BENCHMARKS-METHODOLOGY.md`](BENCHMARKS-METHODOLOGY.md)).
> See §"v0.10.x additions" near
> the bottom of this file for what changed since v0.9, and `CHANGELOG.md`
> for the full per-version delta.

A skill + runtime overlay that turns any modern AI coding tool into a
complete **Full Agentic Operating System**.  The kit was first built up to
v0.9 (30 original subsystems); v0.10.x layered the VIBECODE-MASTER
methodology (RRI + RRI-T + RRI-UX + RRI-UI + 8-step workflow) and the
v0.11.0 security-hardening pass on top.  The table below documents the
*origin* version of each subsystem — historical context, not the current
release:

| # | Subsystem                      | Introduced | Module                | Probe |
|---|--------------------------------|-----------:|-----------------------|------:|
| A | Background-task runtime        |       v0.8 | `task_runtime.py`     | 19    |
| B | MCP client adapter             |       v0.8 | `mcp_client.py`       | 20    |
| C | Cost / token ledger            |       v0.8 | `cost_ledger.py`      | 21    |
| D | 26 lifecycle hook events       |       v0.8 | `hook_interceptor.py` | 22    |
| E | Follow-up re-execute loop      |       v0.8 | `query_loop.py`       | 23    |
| F | fcntl-locked denial store      |       v0.8 | `denial_store.py`     | 24    |
| G | 3-tier memory hierarchy        |       v0.9 | `memory_hierarchy.py` | 25    |
| H | Approval / elicitation UI      |       v0.9 | `approval_contract.py`| 26    |
| I | All 7 task kinds wired         |       v0.9 | `task_runtime.py`     | 27    |
| J | Dream 4-phase + embedding dedup|       v0.9 | `task_runtime.py`     | 28    |
| K | MCP stdio integration round-trip|      v0.9 | `mcp_client.py`       | 29    |
| L | Structured notifications (lock) |      v0.9 | `task_runtime.py`     | 30    |

The conformance audit (`python -m vibecodekit.cli audit`) now runs
**87 internal regression probes** at current main (30 OS + methodology +
packaging/wiring + integration invariants) — an internal self-test
that verifies the runtime has not regressed against its own
specification (see [`BENCHMARKS-METHODOLOGY.md`](BENCHMARKS-METHODOLOGY.md)
for what this measures and does not measure).  The table above shows the
*originally-introduced-in* version of each subsystem; all rows remain
active and have been re-tested on every subsequent release.

## What you get — v0.8 ≡ v0.7 + 6 subsystems

Everything in v0.7.1, plus:

1. **Background tasks** — 7 types (`local_bash`, `local_agent`, `remote_agent`,
   `in_process_teammate`, `local_workflow`, `monitor_mcp`, `dream`), 5 states
   (`pending|running|completed|failed|killed`), on-disk outputs read by
   `offset/length` (Giải phẫu §7.4), task notifications, stall detection.
2. **MCP client** — register any MCP server (`stdio` or `inproc` transport),
   list/call tools, disable.  Enables DBs, filesystems, APIs as
   additional tool providers.
3. **Cost/telemetry ledger** — per-turn tokens, per-tool latency,
   per-model cost estimate in USD.  Written to `.vibecode/runtime/ledger.jsonl`
   and rolled up into `ledger-summary.json` at the end of each query loop.
4. **26 hook events** — Tool lifecycle / Permission / Session / Agent /
   Task / Context / Filesystem / UI-Config.  Plugin-defined hooks run
   with secret-scrubbed payloads (env var filter + JSON walk + token-shape
   regexes for AWS/OpenAI/GitHub/GitLab keys).
5. **Follow-up re-execute** — `retry_same`, `retry_with_budget`,
   `compact_then_retry`, `safe_mode_retry` now actually re-run the turn
   (bounded by `DEFAULT_MAX_FOLLOW_UPS = 3`).
6. **Concurrency-safe denial store** — fcntl exclusive lock + atomic
   `os.replace` so eight parallel partition threads never drop a denial.

v0.7 foundations (still present):

* Disciplined **query loop** (Pattern #1) with derived `needs_follow_up`
  (Pattern #2) and an escalating recovery ladder (Pattern #3).
* **Concurrency-safe tool partitioner** (Pattern #4).
* **Streaming tool executor** (Pattern #5) with path-safety, truncation,
  hook interception and context modifier emission.
* **6-layer permission pipeline** (Pattern #10) — 60+ dangerous patterns
  across k8s / terraform / docker / cloud CLIs / SQL / shell injection /
  sensitive-path reads / sysadmin commands / archive-extract to root.
* **Sub-agent roles with real ACLs** (Pattern #7) — coordinator / scout /
  builder / qa / security.
* **Git-worktree fork isolation** (Pattern #8).
* **Five-layer context defense** (Pattern #9).
* **Conditional skill activation** (Pattern #11).
* **Reconciliation-based install** (Pattern #16).

## When the skill fires

- User issues `/vibe-run <plan.json>` — kicks off the query loop.
- Agent opens any file in `paths` — conditional activation emits a hint in
  chat showing how to engage the 8-step Vibecode methodology.
- Project has `.claw.json` — the skill's hooks are wired into the
  `claw-code` lifecycle automatically.

## The 8 Vibecode steps (short form)

| # | Step                | Tool / template                                  |
|---|---------------------|--------------------------------------------------|
| 1 | Blueprint           | `assets/templates/blueprint.md`                  |
| 2 | Scan                | `assets/templates/scan-report.md`                |
| 3 | TIP                 | `assets/templates/tip.md`                        |
| 4 | Execute             | `python -m vibecodekit.cli run <plan.json>`      |
| 5 | Verify              | `assets/templates/verify-report.md`              |
| 6 | Complete            | `assets/templates/completion-report.md`          |
| 7 | Conform             | `python -m vibecodekit.cli audit --json`         |
| 8 | Release gate        | `python -m vibecodekit.scripts.release` (quality |
|   |                     | gate + quality_gate.evaluate())                  |

## Roles — the 5 RRI personas

| Role                | Scope                                                                  |
|---------------------|------------------------------------------------------------------------|
| Project Architect   | Blueprint, decisions log, risk register, release sign-off              |
| Implementation Lead | TIPs, scope boundaries, tool partition planning                        |
| Verifier            | Writes breaking tests, tries to falsify success claims (Pattern #7 QA) |
| Security Auditor    | Reviews every mutation class 3/4; signs off on bypass mode             |
| Compliance Steward  | Ensures 7-dimension × 8-axis quality gate is met pre-release           |

## File layout

```
skill/vibecodekit-hybrid-ultra/
├── SKILL.md                         (this file)
├── references/                      (deep-dive explanations; see references/00-overview.md)
├── assets/
│   ├── templates/                   (TIP / verify / completion / blueprint / scan / conformance)
│   └── plugin-manifest.json         (declares command/agent/hook exposure)
├── runtime/
│   └── sample-plan.json             (minimal end-to-end plan you can run)
└── scripts/vibecodekit/             (the runtime package — importable as `vibecodekit`)
```

## Quickstart

```bash
# 1. Install the overlay into your project
python -m vibecodekit.cli install /path/to/myproject --dry-run

# 2. Check health
python -m vibecodekit.cli doctor --root /path/to/myproject

# 3. Run the sample plan
python -m vibecodekit.cli run \
    skill/vibecodekit-hybrid-ultra/runtime/sample-plan.json \
    --root /path/to/myproject

# 4. Inspect the event log
python -m vibecodekit.cli dashboard --root /path/to/myproject

# 5. Verify conformance
python -m vibecodekit.cli audit --threshold 0.85
```

## Safety defaults

- **Safe-by-default**: unknown tools are treated as exclusive, unknown
  commands are classified as mutations, and dangerous patterns are denied
  even in `bypass` mode without an explicit `--unsafe` flag.
- **Never deletes** in reconciliation install; orphan files in the
  destination are left alone.
- **Hook env stripped of secrets** by default (`*TOKEN*` / `*KEY*` /
  `*SECRET*` / `*PASSWORD*` / `*CREDENTIAL*` / `*PRIVATE*`).
- **Read budget 200 KB**, result budget 20 KB, command timeout 5 min.

See `references/00-overview.md` for a complete tour.
