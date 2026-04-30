"""Escalating recovery (Pattern #3).

Mirrors ``query.ts:1188-1242`` from Claude Code (Giải phẫu §3.8).  Each
recovery level runs **at most once per turn**; a failure at level N escalates
to level N+1 rather than retrying level N.  The circuit-breaker flag
``hasAttemptedReactiveCompact`` has a direct equivalent in
``RecoveryLedger.attempted``.

References:
- ``references/03-escalating-recovery.md``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# Ordered list of recovery actions (smallest → largest effect).
LEVELS: list[str] = [
    "retry_same",  # 1. retry exactly as before (once)
    "retry_with_budget",  # 2. enlarge context budget (no-op in v0.7 overlay)
    "compact_then_retry",  # 3. reactive compact, then retry
    "safe_mode_retry",  # 4. fallback to plan mode
    "inject_recovery_hint",  # 5. tell the model what went wrong
    "surface_user_decision",  # 6. escalate to the operator
    "terminal_error",  # 7. terminal state: recovery_exhausted
]


@dataclass
class RecoveryLedger:
    """Per-turn ledger — each level may be attempted at most once."""

    attempted: set[str] = field(default_factory=set)
    history: list[dict[str, Any]] = field(default_factory=list)

    def escalate(self, error_kind: str) -> dict[str, Any]:
        # Permission denial has a dedicated early exit — surface to user.
        if error_kind == "permission_denied" and "surface_user_decision" not in self.attempted:
            self.attempted.add("surface_user_decision")
            rec = {"action": "surface_user_decision", "reason": "permission_denied"}
            self.history.append(rec)
            return rec
        # Context-overflow family jumps straight to compact_then_retry.
        if (
            error_kind in ("context_overflow", "prompt_too_large")
            and "compact_then_retry" not in self.attempted
        ):
            self.attempted.add("compact_then_retry")
            rec = {"action": "compact_then_retry", "reason": error_kind}
            self.history.append(rec)
            return rec
        # Otherwise walk the ladder in order.
        for level in LEVELS:
            if level in self.attempted:
                continue
            self.attempted.add(level)
            rec = {"action": level, "reason": error_kind}
            self.history.append(rec)
            return rec
        rec = {"action": "terminal_error", "reason": error_kind, "terminal": "recovery_exhausted"}
        self.history.append(rec)
        return rec

    def reset(self) -> None:
        self.attempted.clear()
        self.history.clear()

    def to_dict(self) -> dict[str, Any]:
        return {"attempted": sorted(self.attempted), "history": list(self.history)}


# ---------------------------------------------------------------------------
# CLI for debugging
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Simulate escalating recovery.")
    ap.add_argument("errors", nargs="+", help="error kinds, e.g. tool_failed context_overflow")
    args = ap.parse_args()
    ledger = RecoveryLedger()
    for e in args.errors:
        print(json.dumps(ledger.escalate(e), indent=2))


if __name__ == "__main__":
    _main()
