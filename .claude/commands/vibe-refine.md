---
description: Refine ticket (step 8/8) — open template + classify diff against the v5 refine envelope
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-30, ref-36]
---

# /vibe-refine

REFINE is BƯỚC 8/8 of the v5 VIBECODE pipeline.  This command opens the
refine ticket template and exposes the boundary classifier so you cannot
accidentally smuggle a structural change (new route, dependency bump,
schema migration) through the refine path.

## Usage

```bash
# 1) Open the refine ticket template
cat ai-rules/vibecodekit/templates/refine.md

# 2) Classify a candidate diff (in_scope vs requires_vision)
git diff main... | vibecodekit refine classify -

# 3) Or pass a saved patch file
vibecodekit refine classify path/to/change.patch
```

Exit codes:
- `0` → `in_scope` (refine allowed)
- `1` → `requires_vision` (re-run BƯỚC 3 first)

## Boundary rules (canonical)

- ✅ **In scope:** copy / text / VN localisation, minor CSS-token /
  colour / spacing tweaks, content edits inside existing sections,
  localised verify-report fixes.
- ⛔ **Out of scope (cần VISION):** new routes / pages / API endpoints,
  new top-level components, dependency bumps, `prisma/schema.prisma` or
  migration changes, `next.config.*` / `tsconfig.json` /
  `tailwind.config.*` edits, file renames, new module folders, CI/CD
  workflow edits.

## References

- `ai-rules/vibecodekit/references/30-vibecode-master.md` §8 (REFINE
  envelope, canonical limits)
- `ai-rules/vibecodekit/references/29-rri-reverse-interview.md` (the
  step you must loop back to when classifier returns `requires_vision`)
- `ai-rules/vibecodekit/references/32-rri-ux-critique.md` §10 (12 SaaS
  anti-patterns the refine must not introduce)

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-refine
```

**Wired references:** ref-30, ref-36 — loaded verbatim by `methodology.render_command_context`.

<!-- v0.11.3-runtime-wiring-end -->
