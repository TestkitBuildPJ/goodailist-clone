# Pattern #7 — Coordinator restriction

**Source:** `coordinatorMode.ts:29-34` (Giải phẫu §6.3)

## Rule
A coordinator agent has **four tools** (create team, send message, finish,
and list_files in Claude Code).  It cannot `FileWrite`, `Bash`, or `Edit`.
The restriction is enforced at the **tool loader**, not in the prompt.

## Why this works
Instruction-level constraints are probabilistic — agents under stress
sometimes violate them.  Capability-level constraints are deterministic:
the call literally isn't in the agent's vocabulary.

## v0.7 role cards

| Role        | `can_mutate` | Allowed tools                                                    |
|-------------|:------------:|------------------------------------------------------------------|
| coordinator |     no       | list_files, read_file, grep, glob                                |
| scout       |     no       | list_files, read_file, grep, glob, run_command (plan mode)       |
| builder     |     yes      | everything except delete_file; high-risk bubbles up              |
| qa          |     no       | list_files, read_file, grep, glob, run_command (plan mode)       |
| security    |     no       | list_files, read_file, grep, glob, run_command (plan mode)       |

## How v0.7 enforces it
- `tool_executor.execute_one()` checks `profile["tools"]` before dispatch.
- `subagent_runtime.run()` also vetoes write-class blocks up-front so the
  rejection is **per-plan**, not just per-tool.
- Probe `07_coordinator_restriction`: a coordinator issued a `write_file`
  must be rejected with `rejected=True`.
