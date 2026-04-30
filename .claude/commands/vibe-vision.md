---
description: Open the Vision template (Contractor proposal before Blueprint)
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-30, ref-34]
---

# /vibe-vision — Project type + stack + layout proposal

Before BLUEPRINT, the Contractor proposes a Vision: project type,
stack, layout, style direction, and non-negotiables.  Homeowner replies
`APPROVED` / `ADJUST` / `REJECT`.

## Usage

```bash
cat ai-rules/vibecodekit/templates/vision.md
cat ai-rules/vibecodekit/references/30-vibecode-master.md
```

## Project types auto-detected
- Landing page / SaaS / Dashboard / Blog / Docs / Portfolio /
  E-commerce / Enterprise-module / Custom

## Output
`docs/vision/<project>-vision.md` — locked by Homeowner `APPROVED`.
Changing a Vision after Blueprint requires a new VISION step.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-vision \
  --project-type <type>
```

**Wired references:** ref-30, ref-34 — loaded verbatim by `methodology.render_command_context`.

**Dynamic data sources:** recommend_stack — pulled at runtime per project context.

<!-- v0.11.3-runtime-wiring-end -->
