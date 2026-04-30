# Pattern #9 — Five-layer context defense

**Source:** `services/compact/` 3 971 LOC (Giải phẫu §8)

## Escalating ladder

| Layer | Name                      | Cost       | Trigger                                      |
|-------|---------------------------|------------|----------------------------------------------|
|   1   | Tool-result truncation    | ~zero      | output > `maxResultSizeChars`                |
|   2   | Microcompact              | 0 LLM      | token pressure approaching context window    |
|   3   | Auto-compact              | 1 LLM call | token pressure crosses `effective_ctx_win`   |
|   4   | Reactive compact          | 1 LLM call | API 413 (`prompt_too_long`)                  |
|   5   | Context collapse          | ~zero      | even after reactive compact, conv. too large |

**Each layer runs at most once per turn** — `hasAttemptedReactiveCompact`
is a circuit breaker.

## v0.7 artefacts on disk

| File                                    | Emitted by                |
|-----------------------------------------|---------------------------|
| `.vibecode/runtime/tool-results.truncated.txt` | Layer 1            |
| `.vibecode/runtime/compact-boundary.json`      | Layer 3            |
| `.vibecode/runtime/reactive-compact.json`      | Layer 4            |
| `.vibecode/runtime/context-collapse.json`      | Layer 5            |

## What gets kept (Layer 5)
Documented at `_COLLAPSE_KEEPS`:
`blueprint`, `requirements`, `decision_log`, `active_tip`, `risks`,
`security_constraints`, `business_rules`, `latest_observations`,
`open_questions`, `release_decision`.

## How v0.7 enforces it
- `compaction.compact()` runs layers 1-3 always; 4-5 on `reactive=True` or
  `raw_chars ≥ 120 000`.
- Probe `09_five_layer_context_defense`: when 2 000 events are emitted and
  reactive=True, layers {2,3,4,5} must all appear in the result.
