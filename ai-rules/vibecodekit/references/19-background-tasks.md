# 19 — Background-task runtime (Giải phẫu §7)

## What the book says

The agent loop is synchronous, but real-world work is not: long builds,
test suites, linters, remote deployments, and *dream* consolidations all
have to run **outside** the foreground turn.  Giải phẫu §7 defines a
background-task subsystem with seven kinds and five lifecycle states,
exposing output via an **`outputOffset`** read pattern so the foreground
loop can pull incremental progress without re-reading.

## How v0.8 implements it

Module: `scripts/vibecodekit/task_runtime.py`.

### Task kinds (§7.2)

```
local_bash             # local shell process
local_agent            # spawned sub-agent with its own query loop
remote_agent           # agent on a remote runner (stub)
in_process_teammate    # teammate in coordinator mode (stub)
local_workflow         # scripted pipeline (stub)
monitor_mcp            # MCP server health monitor (stub)
dream                  # memory-consolidation between sessions
```

Only `local_bash` and `dream` are fully implemented in v0.8; the other
five have scaffolding so that v0.8.x / v0.9 can add executors without
migrating the task record format.

### States (§7.3)

```
pending → running → completed
                   ↘ failed
                   ↘ killed
```

State transitions are written to `.vibecode/runtime/tasks/index.json`
under an `fcntl.flock(LOCK_EX)` + atomic `os.replace`.

### Output (§7.4)

Each task writes to `.vibecode/runtime/tasks/<id>.out`.  Reads use the
**outputOffset** pattern:

```python
r0 = read_task_output(root, task_id, offset=0, length=4096)
r1 = read_task_output(root, task_id, offset=r0["next_offset"], length=4096)
```

The return contains `content`, `next_offset`, `eof`, and `stdout_size`.

### Notifications

`.vibecode/runtime/tasks/<id>.notifications.jsonl` is an append-only
ledger of `task_created`, `task_completed`, `task_failed`, `task_killed`,
`task_stalled` events.  `drain_notifications()` returns all pending
entries and truncates the file.

### Stall detection

`check_stalls()` inspects each running task.  If no bytes were written
for **≥ 45 s** and the tail matches an interactive prompt regex
(`/[Yyn\?]/`), a `task_stalled` notification is emitted.

### Dream

`start_dream()` launches a background thread that reads the last 200
events from all ``*.events.jsonl`` logs, computes a four-phase digest
(*orient / gather / consolidate / prune*) and writes
`.vibecode/memory/dream-digest.md`.

## CLI surface

```bash
vibe task --root . start "long-build.sh"  --timeout 3600
vibe task --root . list
vibe task --root . read <task_id> --offset 0 --length 4096
vibe task --root . status <task_id>
vibe task --root . kill <task_id>
vibe task --root . stalls
vibe task --root . dream
```

## Audit probe

`19_background_tasks` starts a `local_bash` task, waits for completion,
reads bytes 4..8 of the output with `offset=4, length=4`, and verifies
`types=7 states=5 offset_ok=True`.
