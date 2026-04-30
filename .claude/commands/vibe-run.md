---
description: Run a Vibecode plan through the query loop
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-run

Run a Vibecode plan through the query loop.

## Usage
```bash
python -m vibecodekit.cli run ${1:-runtime/sample-plan.json} --root . --mode default
```

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.

## References

- `ai-rules/vibecodekit/references/01-async-generator-loop.md`
- `ai-rules/vibecodekit/references/02-derived-needs-follow-up.md`
- `ai-rules/vibecodekit/references/03-escalating-recovery.md`
