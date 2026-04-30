# Pattern #3 — Escalating recovery

**Source:** `query.ts:1188-1242` (Giải phẫu §3.8)

## The ladder (in order)

| Level | Action                   | Side-effect (v0.7)                           |
|-------|--------------------------|----------------------------------------------|
| 1     | `retry_same`             | Re-dispatch the failed block verbatim.        |
| 2     | `retry_with_budget`      | Retry with a larger context budget (no-op in overlay). |
| 3     | `compact_then_retry`     | Run `compact(reactive=True)` → retry.         |
| 4     | `safe_mode_retry`        | Switch permission mode to `plan`.             |
| 5     | `inject_recovery_hint`   | Emit `recovery_hint_injected` so the model re-plans. |
| 6     | `surface_user_decision`  | Halt and ask the operator.                    |
| 7     | `terminal_error`         | `query_end` with status `recovery_exhausted`. |

## Invariants
- **Each level runs at most once per turn** (`RecoveryLedger.attempted`).
- **Permission denials jump to level 6** — never loop on a user decline.
- **Context overflow jumps to level 3** — no point retrying at level 1.
- **Terminal state is observable**: a consumer can tell "recovery exhausted"
  from the event `terminal_error`.

## How v0.7 enforces it
- `recovery_engine.RecoveryLedger.escalate()` implements the ladder.
- `query_loop._dispatch_recovery()` executes the side-effect for every
  level (this was the v0.6 regression — only `terminal_error` was wired).
- Probes `03_escalating_recovery` and `02_derived_needs_follow_up` exercise
  the ladder.
