---
description: Open the blueprint template
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-30]
agent: coordinator
---

# /vibe-blueprint

Open the blueprint template.

## Usage
```bash
cat ai-rules/vibecodekit/templates/blueprint.md
```

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-blueprint
```

**Wired references:** ref-30 — loaded verbatim by `methodology.render_command_context`.

**Default agent:** `coordinator` (auto-spawned via `subagent_runtime.spawn_for_command`).  Override per command by editing the `agent:` frontmatter field.

<!-- v0.11.3-runtime-wiring-end -->
