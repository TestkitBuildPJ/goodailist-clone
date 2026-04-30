---
description: Dry-run a command through the 6-layer permission pipeline
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-permission

Dry-run a command through the 6-layer permission pipeline.

## Usage
```bash
python -m vibecodekit.cli permission "${1}" --mode ${2:-default}
```

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.

## References

- `ai-rules/vibecodekit/references/10-permission-classification.md`
- `ai-rules/vibecodekit/references/15-plugin-sandbox.md`
- `ai-rules/vibecodekit/references/23-permission-matrix.md`
