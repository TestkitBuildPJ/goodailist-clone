# Pattern #1 — Async generator as control flow

**Source:** `query.ts:219-241` (Claude Code, 513 K LOC leak — Giải phẫu §3.4)

## Problem
A push-based (callback / event emitter) loop for LLM tool use forces the
caller to reason about *when* each event fires.  A pull-based async
generator lets the *consumer* decide the pace: read one event, pause, read
another.  This is essential for tool streaming (Pattern #5) and for
back-pressure when a human-in-the-loop approves or rejects a call.

## Claude Code implementation (abridged)
```ts
export async function* query(opts): AsyncGenerator<QueryEvent> {
  while (true) {
    const stream = await callLLM(opts.messages);
    let needsFollowUp = false;
    for await (const block of stream) {
      yield {type: "block", block};
      if (block.type === "tool_use") {
        const batch = partitionToolCalls([block]);
        for (const r of await executeBatch(batch)) {
          yield {type: "tool_result", result: r};
        }
        needsFollowUp = true;                     // Pattern #2
      }
    }
    if (!needsFollowUp) return;
  }
}
```

## v0.7 adaptation
We can't literally import the LLM stream, but the same control-flow
semantics are preserved: `query_loop.run_plan()` iterates one turn at a time,
executes each turn's tool uses, and only continues when
``needs_follow_up`` is observably true.

## How v0.7 enforces it
- `query_loop.run_plan()` never runs a turn past the point where
  `turn_results[-1]` has an unrecoverable error.
- Probe `01_async_generator_loop`: plan with one turn must finish with
  `stop_reason == "plan_exhausted"`.
