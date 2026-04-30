---
description: Open the SCAN template — read-only repo exploration
version: 0.11.3
allowed-tools: [Bash, Read]
agent: scout
---

# /vibe-scan — Read-only repo scan (step 1 of VIBECODE-MASTER)

Produce a structured report of what's already in the repo: tech stack,
modules, invariants, dependencies, reusable patterns, risks.  This
feeds both RRI (auto-answered questions) and VISION (stack proposal).

## Usage

```bash
cat ai-rules/vibecodekit/templates/scan-report.md
cat ai-rules/vibecodekit/references/30-vibecode-master.md
```

## Scope of SCAN
- **READ-ONLY** — no file mutations
- Structure (2-level `list_files`)
- Framework, language, package manager
- Key modules and their responsibilities
- Dependencies (prod / dev / external services)
- Patterns already in use (matched against `references/` pattern library)
- Invariants the code already enforces
- Gaps: missing tests, missing docs, TODO clusters

## Output
`docs/scan/<timestamp>-scan.md`.  Every SCAN must end with an
"Open questions for Architect" list — these become the first
questions in the RRI interview.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-scan
```

**Default agent:** `scout` (auto-spawned via `subagent_runtime.spawn_for_command`).  Override per command by editing the `agent:` frontmatter field.

<!-- v0.11.3-runtime-wiring-end -->
