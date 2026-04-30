# Pattern #4 — Concurrency-safe partitioning

**Source:** `toolOrchestration.ts:91-120` (Giải phẫu §4.2)

## Core idea
Classification per **invocation**, not per **tool type**.  A `run_command`
with `cmd="ls -la"` is safe; the same tool with `cmd="mkdir"` is not.  That
granularity is what lets Claude Code safely parallelise dozens of reads
while preserving the serial order of writes.

## Algorithm (v0.7 `partition_tool_blocks`)

```text
out = []
for block in blocks:
    safe = is_concurrency_safe(block)   # uses per-invocation predicate
    if safe and out and out[-1].safe:
        out[-1].blocks.append(block)    # merge with previous safe batch
    else:
        out.append(Batch(safe, [block]))
return out
```

## Safe-by-default escape hatches
- Unknown tools                → exclusive
- Malformed input              → exclusive
- Predicate throws             → exclusive

## How v0.7 enforces it
- `tool_schema_registry.partition_tool_blocks()` implements the merge.
- `tool_executor.execute_blocks()` runs safe batches in a thread pool
  (`max_workers=8`) and exclusive batches serially.
- Probe `04_concurrency_partitioning`: `[read, read, write, read]` must
  partition into `[(safe, 2), (unsafe, 1), (safe, 1)]`.
