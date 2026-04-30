---
description: Spawn a sub-agent (coordinator/scout/builder/qa/security)
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-subagent

Spawn a sub-agent (coordinator/scout/builder/qa/security).

## Usage
```bash
python -m vibecodekit.cli subagent spawn ${1:-scout} "${2:-no objective}" --root .
```

See `ai-rules/vibecodekit/SKILL.md` for the full documentation.
