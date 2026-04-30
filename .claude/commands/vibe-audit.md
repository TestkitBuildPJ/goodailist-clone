---
description: Run the 18-pattern conformance audit
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-25, ref-26, ref-32]
agent: security
---

# /vibe-audit

Run the 18-pattern conformance audit.

## Usage
```bash
python -m vibecodekit.cli audit --threshold 0.85
```

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.

## References

- `ai-rules/vibecodekit/references/25-release-governance.md`
- `ai-rules/vibecodekit/references/26-quality-gates.md`

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-audit
```

**Wired references:** ref-25, ref-26, ref-32 — loaded verbatim by `methodology.render_command_context`.

**Default agent:** `security` (auto-spawned via `subagent_runtime.spawn_for_command`).  Override per command by editing the `agent:` frontmatter field.

<!-- v0.11.3-runtime-wiring-end -->
