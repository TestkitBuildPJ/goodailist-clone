# VibecodeKit v0.7 — Overview & Table of Contents

VibecodeKit Hybrid Ultra v0.7 is a **disciplined overlay** that implements
the 18 architectural patterns documented in:

- *Giải phẫu một Agentic Operating System* — Lâm Nguyễn, March 2026
  (Vietnamese dissection of 513 000 LOC of the Claude Code source).
- <https://claude-code-from-source.com/> — interactive web companion.

The references in this folder are the **canonical specification** of what
each v0.7 module must do.  Every reference ends with a "How v0.7 enforces it"
section that ties it back to a runtime probe in
`conformance_audit.py`.

## 18 patterns ↔ v0.7 modules

| #  | Pattern                                  | Module                       | Ref                                     |
|----|------------------------------------------|------------------------------|-----------------------------------------|
|  1 | Async-generator query loop               | `query_loop.py`              | [01-async-generator-loop.md](01-async-generator-loop.md) |
|  2 | Derived `needs_follow_up` flag           | `query_loop.py`              | [02-derived-needs-follow-up.md](02-derived-needs-follow-up.md) |
|  3 | Escalating recovery                      | `recovery_engine.py`         | [03-escalating-recovery.md](03-escalating-recovery.md) |
|  4 | Concurrency-safe partitioning            | `tool_schema_registry.py`    | [04-concurrency-partitioning.md](04-concurrency-partitioning.md) |
|  5 | Streaming tool execution                 | `tool_executor.py`           | [05-streaming-tool-execution.md](05-streaming-tool-execution.md) |
|  6 | Context modifier chain                   | `context_modifier_chain.py`  | [06-context-modifier-chain.md](06-context-modifier-chain.md) |
|  7 | Coordinator restriction                  | `subagent_runtime.py`        | [07-coordinator-restriction.md](07-coordinator-restriction.md) |
|  8 | Fork isolation via Git worktree          | `worktree_executor.py`       | [08-fork-isolation-worktree.md](08-fork-isolation-worktree.md) |
|  9 | 5-layer context defense                  | `compaction.py`              | [09-five-layer-context-defense.md](09-five-layer-context-defense.md) |
| 10 | Permission classification pipeline       | `permission_engine.py`       | [10-permission-classification.md](10-permission-classification.md) |
| 11 | Conditional skill activation             | `skill_discovery.py`         | [11-conditional-skill-activation.md](11-conditional-skill-activation.md) |
| 12 | Shell-in-prompt                          | *policy-only*                | [12-shell-in-prompt.md](12-shell-in-prompt.md) |
| 13 | Dynamic skill discovery                  | `skill_discovery.py`         | [13-dynamic-skill-discovery.md](13-dynamic-skill-discovery.md) |
| 14 | Plugin extension points                  | `hook_interceptor.py` + manifest | [14-plugin-extension.md](14-plugin-extension.md) |
| 15 | Security sandbox for plugins             | `hook_interceptor.py`        | [15-plugin-sandbox.md](15-plugin-sandbox.md) |
| 16 | Reconciliation-based install             | `install_manifest.py`        | [16-reconciliation-install.md](16-reconciliation-install.md) |
| 17 | Pure-TS native module replacement        | *policy-only*                | [17-native-replacement.md](17-native-replacement.md) |
| 18 | Terminal-as-browser rendering            | *policy-only*                | [18-terminal-ui.md](18-terminal-ui.md) |

## Methodology references

| Topic                            | Ref                                                           |
|----------------------------------|---------------------------------------------------------------|
| Vibecode lifecycle & 8 steps     | [20-lifecycle.md](20-lifecycle.md)                            |
| RRI 5 personas + SVPFI signals   | [21-rri-methodology.md](21-rri-methodology.md)                |
| UX/UI quality dimensions         | [22-rri-ux-ui.md](22-rri-ux-ui.md)                            |
| Permission matrix by role        | [23-permission-matrix.md](23-permission-matrix.md)            |
| Memory governance                | [24-memory-governance.md](24-memory-governance.md)            |
| Release governance               | [25-release-governance.md](25-release-governance.md)          |
| Quality gates — 7 dims × 8 axes  | [26-quality-gates.md](26-quality-gates.md)                    |

## v0.11.x extension references (post-`Hybrid Ultra` rollouts)

| Ref | Topic                                                                                       |
|-----|---------------------------------------------------------------------------------------------|
| 27  | [27-mcp-adapter.md](27-mcp-adapter.md) — MCP stdio transport contract                        |
| 28  | [28-cost-ledger.md](28-cost-ledger.md) — Cost accounting ledger format                       |
| 29  | [29-rri-reverse-interview.md](29-rri-reverse-interview.md) — Reverse interview pipeline      |
| 30  | [30-vibecode-master.md](30-vibecode-master.md) — VIBECODE-MASTER 8-step canonical workflow   |
| 31  | [31-rri-t-testing.md](31-rri-t-testing.md) — RRI-T 5×7×8 testing matrix                      |
| 32  | [32-rri-ux-critique.md](32-rri-ux-critique.md) — RRI-UX critique pipeline + 12 anti-patterns |
| 33  | [33-rri-ui-design.md](33-rri-ui-design.md) — RRI-UI four-phase design pipeline               |
| 34  | [34-style-tokens.md](34-style-tokens.md) — FP/CP rosters + VN-01..VN-12 typography rules    |
| 35  | [35-enterprise-module-pattern.md](35-enterprise-module-pattern.md) — Pattern F module workflow |
| 36  | [36-copy-patterns.md](36-copy-patterns.md) — CF-01..CF-09 + CF-VN-01..08 copy rules          |

## Runtime data assets (v0.11.x)

| Asset                                              | Loaded by                                                |
|----------------------------------------------------|----------------------------------------------------------|
| `assets/rri-question-bank.json` (v1.1.0, 293 q)    | `methodology.load_rri_questions(project_type, persona=…, mode=…)` |
| `assets/scaffolds/docs/manifest.json` + nextjs/    | `scaffold_engine.preview('docs', stack='nextjs', …)`     |
| `assets/scaffolds/{landing-page,saas,portfolio,…}` | `scaffold_engine.list_presets()` (10 presets total)      |
