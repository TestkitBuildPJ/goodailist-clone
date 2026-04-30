# Pattern #2 — Derive `needs_follow_up` from observable behaviour

**Source:** `query.ts:557-559` (Giải phẫu §3.5)

## Problem
A model's `stop_reason` metadata can lie: the API may say `"end_turn"` even
though the response has unprocessed tool-use blocks, and vice-versa.
Claude Code therefore *ignores* the API hint and instead **observes the
stream**: if any tool-use block was emitted, follow-up is required; if the
last result contains an error, follow-up is required; otherwise stop.

## v0.7 derivation rules
`needs_follow_up` is true iff any of:
1. The turn produced ≥ 1 tool use, and any result has `status != "ok"`.
2. The turn explicitly set `stop_reason == "work_remaining"` in its plan.
3. A recovery action was dispatched.

It is **not** enough for the LLM to say "done" — the *behaviour* decides.

## How v0.7 enforces it
- `query_loop.run_plan()` calls `_classify_error()` per result and consults
  `RecoveryLedger.escalate()`.
- Probe `02_derived_needs_follow_up`: a plan whose first turn reads a
  non-existent file must populate `ledger.history` with at least one
  recovery action.
