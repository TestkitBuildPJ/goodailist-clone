---
description: Pattern F — add a new module to an existing codebase (reuse-max / build-min)
version: 0.11.3
allowed-tools: [Bash, Read, Write]
wired_refs: [ref-35]
agent: builder
---

# /vibe-module

Pattern F of the v5 spec: the user already has a working codebase and
wants to **add a feature module without rebuilding from scratch**.  The
golden rule is **reuse-max / build-min** — every line of new code must
be justified against an inventory of what the existing codebase already
provides.

## When to use

| Situation | Use |
|-----------|-----|
| Empty directory, no `package.json` | `/vibe-scaffold` (Pattern A/B/C/D/E) |
| Existing codebase, want to add module | **`/vibe-module`** (Pattern F) |
| Just text/copy/colour tweak | `/vibe-refine` (BƯỚC 8/8) |

## Workflow

```bash
# 1. Probe — what does the existing codebase already give us?
python -m vibecodekit.cli module probe ./my-app

# 2. Plan — generate a reuse-max/build-min module plan
python -m vibecodekit.cli module plan \
  --name "billing" \
  --spec "Subscription checkout + usage metering" \
  --target ./my-app

# 3. Drop the plan JSON into the module-spec.md template
cat assets/templates/module-spec.md
```

The probe detects: **Next.js**, **React**, **Vite**, **Prisma**,
**NextAuth**, **Tailwind**, **Express**, **FastAPI**, **Django**,
**TypeScript**.  Each detected capability lands in the **REUSE
INVENTORY** with a one-line hint on how to reuse it.  Anything
unsupported by the existing stack falls into the **NEW BUILD** list and
flags itself in the `risks` array.

## Refusal contract

`generate_module_plan()` raises `EmptyCodebaseError` when the target
directory contains no project marker
(`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` / `Gemfile`
/ `composer.json` / `pom.xml` / `build.gradle`).  This is intentional —
Pattern F **requires** an existing codebase; empty targets must go
through `/vibe-scaffold` first.

## Output schema

```json
{
  "name": "billing",
  "spec": "...",
  "reuse_inventory": [
    {"capability": "nextjs", "evidence": "package.json: next@15.0.0",
     "reuse_hint": "App Router pages — extend `app/<route>/`"},
    ...
  ],
  "new_files": ["app/billing/page.tsx", "app/api/billing/route.ts", ...],
  "acceptance_criteria": ["Module entrypoint reachable", ...],
  "target_dirs": ["app/billing"],
  "risks": ["Module routes must call getServerSession()", ...],
  "requires_existing_codebase": true
}
```

Hand the JSON straight to `/vibe-blueprint` (which already accepts a
plan input) and `/vibe-tip` (which expands `new_files` into TIPs).

## References

* `ai-rules/vibecodekit/references/30-vibecode-master.md` Pattern F
* `ai-rules/vibecodekit/references/35-enterprise-module-pattern.md`
  (this kit's reuse-max/build-min checklist)
* `ai-rules/vibecodekit/references/29-rri-reverse-interview.md` (the
  RRI step that owns *new* feature surface)

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-module
```

**Wired references:** ref-35 — loaded verbatim by `methodology.render_command_context`.

**Default agent:** `builder` (auto-spawned via `subagent_runtime.spawn_for_command`).  Override per command by editing the `agent:` frontmatter field.

<!-- v0.11.3-runtime-wiring-end -->
