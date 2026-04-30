# Pattern #6 — Context modifier chain

**Source:** `Tool.ts:329`, `StreamingToolExecutor.ts:385` (Giải phẫu §4.4)

## Problem
If any tool can mutate shared state directly, parallelism becomes unsound.
Claude Code therefore has every tool return a **modifier**: a small,
declarative description of the intended state change.  A serial chain then
applies the modifiers in order, producing a new immutable context.

## v0.7 modifier kinds

| Kind          | Shape                                                          |
|---------------|----------------------------------------------------------------|
| `file_changed`| `{"kind": "file_changed", "path": "src/foo.py"}`               |
| `artifact`    | `{"kind": "artifact", "path": "...", "sha256": "..."}`         |
| `memory_fact` | `{"kind": "memory_fact", "text": "Decided X because Y."}`      |
| `denial`      | `{"kind": "denial", "action": "...", "reason": "..."}`         |
| `task_status` | `{"kind": "task_status", "task_id": "...", "status": "done"}`  |

## v0.7 semantics
- Modifiers are emitted by **exclusive** tools only (safe ones by definition
  don't mutate state).
- `apply_modifiers()` is called **after** each batch — never interleaved
  with the batch itself.
- The resulting context snapshot is persisted to
  `.vibecode/runtime/context.json` on every turn.

## How v0.7 enforces it
- `context_modifier_chain.apply_modifiers()` — deterministic, no threads.
- `tool_executor.execute_blocks()` collects modifiers from exclusive
  batches only.
- Probe `06_context_modifier_chain`: two modifiers produce the expected
  keys in the resulting context.
