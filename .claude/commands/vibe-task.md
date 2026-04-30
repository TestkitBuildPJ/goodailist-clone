---
description: Background-task runtime (7 kinds, 5 states)
version: 0.11.2
allowed-tools: [Bash, Read]
---

# /vibe-task

Drive the background-task runtime (Giải phẫu Ch 7).  All tasks persist to
`.vibecode/runtime/tasks/<task-id>.*` so a host UI can read progress.

## Usage
```bash
# Kick off a shell task with a timeout
python -m vibecodekit.cli task start "pytest -q" --timeout 120

# Spawn a sub-agent with a block-plan
python -m vibecodekit.cli task agent \
  --role scout --objective "find TODOs" \
  --blocks '[{"tool":"grep","input":{"pattern":"TODO","path":"."}}]'

# Declarative workflow (bash + write + sleep steps)
python -m vibecodekit.cli task workflow ./workflow.json

# Monitor an MCP server (pings on an interval)
python -m vibecodekit.cli task monitor --server selfcheck --tool ping \
  --interval 30 --max-checks 20

# DreamTask — 4-phase memory consolidation (orient→gather→consolidate→prune)
python -m vibecodekit.cli task dream

# Utility commands
python -m vibecodekit.cli task list --only running
python -m vibecodekit.cli task status <task-id>
python -m vibecodekit.cli task read   <task-id> --offset 0 --length 8192
python -m vibecodekit.cli task kill   <task-id>
python -m vibecodekit.cli task stalls
```

## References

- `ai-rules/vibecodekit/references/19-background-tasks.md`
