# Pattern #5 — Streaming tool execution

**Source:** `StreamingToolExecutor.ts` 530 LOC (Giải phẫu §4.3)

## Problem
Waiting for a whole LLM response before dispatching the first tool wastes
latency.  Claude Code starts executing tool uses **as they stream in**, and
merges results back into the conversation incrementally.

## v0.7 adaptation
The overlay does not itself consume an LLM stream — the caller provides a
plan.  But the executor is **block-level streaming**:

- Each block is permission-checked, hook-gated, and dispatched independently.
- Safe batches are parallelised; results are yielded as each future
  completes (`concurrent.futures.as_completed`).
- Every yielded result is written to the `event_bus` before the next one
  starts, so a dashboard can tail the run in real time.

## Result budget (Pattern #9 layer 1 tie-in)
- Command stdout/stderr truncated at 20 KB.
- `read_file` truncated at 200 KB; the result always carries
  `truncated: bool` so the caller can recover (re-read narrower slice, or
  load from disk via follow-up tool call).

## How v0.7 enforces it
- `tool_executor._tool_run_command`, `_tool_read_file` implement caps.
- `tool_executor.execute_blocks` uses `ThreadPoolExecutor` + `as_completed`.
- Probe `05_streaming_tool_execution`: two reads must both succeed.
