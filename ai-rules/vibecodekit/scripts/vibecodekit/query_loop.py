"""Async-generator style query loop (Pattern #1).

Drives a plan of ``turns``; each turn has ``tool_uses`` (blocks to execute).
``needs_follow_up`` is derived from observable behaviour (Pattern #2):

    - the turn produced a tool use          → continue
    - OR the last result has status != ok   → continue (recovery will decide)
    - OR the turn set ``stop_reason`` = "work_remaining" → continue
    - OR ``max_turns`` not yet reached AND plan has more turns

…else the loop halts with a ``terminal_state`` event.  All recovery paths
are dispatched (this is the v0.6 regression — only terminal_error was).

References:
- ``references/02-derived-needs-follow-up.md``
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .approval_contract import create as create_approval
from .compaction import compact
from .cost_ledger import record_tool, record_turn
from .cost_ledger import summary as ledger_summary
from .event_bus import EventBus
from .hook_interceptor import run_hooks
from .recovery_engine import RecoveryLedger
from .tool_executor import execute_blocks

DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_FOLLOW_UPS = 3  # number of automatic re-executions per turn


def _classify_error(result: dict) -> str | None:
    """Map a tool-execution result to a recovery-engine error kind."""
    if result.get("status") == "blocked":
        return "permission_denied"
    perm = (result.get("result") or {}).get("permission")
    if isinstance(perm, dict) and perm.get("decision") == "deny":
        return "permission_denied"
    inner = result.get("result") or {}
    err = inner.get("error") or ""
    if "path escapes" in err:
        return "path_escape"
    if inner.get("truncated") and inner.get("bytes"):
        return "tool_output_too_large"
    rc = inner.get("returncode")
    if isinstance(rc, int) and rc not in (0, None):
        return "command_failed"
    if result.get("status") not in ("ok", None):
        return "tool_failed"
    return None


def _dispatch_recovery(root: Path, action: str, bus: EventBus, mode: str) -> dict[str, Any]:
    """Execute the side-effect of a recovery action."""
    if action == "compact_then_retry":
        out = compact(root, reactive=True)
        bus.emit("recovery_compact", "ok", {"layers": out["layers"]})
        return {"ok": True, "action": action, "compact": out}
    if action == "safe_mode_retry":
        bus.emit("recovery_safe_mode", "ok", {"requested_mode": "plan"})
        return {"ok": True, "action": action, "new_mode": "plan"}
    if action == "inject_recovery_hint":
        bus.emit("recovery_hint_injected", "ok", {})
        return {"ok": True, "action": action, "hint": "Model should re-plan the failing turn."}
    if action == "surface_user_decision":
        # v0.9: emit a structured approval record instead of just a bare
        # event so a host UI can render a decision card.
        appr = create_approval(
            root,
            kind="permission",
            title="Recovery requires a user decision",
            summary="Automatic recovery exhausted; please choose how to proceed.",
            risk="high",
            reason="query_loop recovery ladder reached surface_user_decision",
            context={"mode": mode},
            options=[
                {"id": "retry", "label": "Retry the turn in safe mode"},
                {"id": "abort", "label": "Abort the plan", "default": True},
                {"id": "ignore", "label": "Skip this turn and continue"},
            ],
            suggested="abort",
        )
        bus.emit("recovery_ask_user", "ok", {"approval_id": appr["id"], "approval": appr})
        return {"ok": True, "action": action, "surface": True, "approval_id": appr["id"]}
    if action == "retry_same":
        bus.emit("recovery_retry_same", "ok", {})
        return {"ok": True, "action": action}
    if action == "retry_with_budget":
        bus.emit("recovery_budget_retry", "ok", {})
        return {"ok": True, "action": action}
    if action == "terminal_error":
        bus.emit("terminal_error", "error", {"reason": "recovery_exhausted"})
        return {"ok": False, "action": action, "terminal": True}
    return {"ok": False, "action": action, "unknown": True}


def run_plan(
    plan: dict,
    *,
    root: str = ".",
    mode: str = "default",
    rules: list[dict] | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> dict[str, Any]:
    root_p = Path(root).resolve()
    bus = EventBus(root_p)
    ledger = RecoveryLedger()
    turns: list[dict] = plan.get("turns") or []

    run_hooks(root_p, "pre_query", {"plan": plan, "mode": mode})
    bus.emit("query_start", "ok", {"turns": len(turns), "mode": mode})

    context: dict[str, Any] = {}
    turn_results: list[dict] = []
    stop_reason = "max_turns"
    current_mode = mode

    for i, turn in enumerate(turns[:max_turns]):
        turn_idx = i + 1
        # v0.9 P1-1 fix: the recovery ladder is *per turn* (docstring says
        # so).  Reset state before each turn so the 7 levels are available
        # for every turn, not just the first.
        ledger.reset()
        bus.set_turn(turn_idx)
        bus.emit(
            "turn_start", "ok", {"turn": turn_idx, "mode": current_mode, "title": turn.get("title")}
        )
        blocks = turn.get("tool_uses") or turn.get("blocks") or []
        if not blocks:
            bus.emit("turn_skip_no_blocks", "ok", {"turn": turn_idx})
            continue

        # Approximate prompt tokens from the block JSON for cost accounting.
        prompt_repr = json.dumps(blocks, ensure_ascii=False)
        follow_up_count = 0
        needs_follow_up = False
        exec_result: dict[str, Any] = {"results": []}

        while True:
            t0 = time.monotonic()
            exec_result = execute_blocks(
                root_p, blocks, session_id=bus.session_id, mode=current_mode, rules=rules
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            # Telemetry — one tool-timing record per block (§12.4)
            for res in exec_result.get("results") or []:
                tname = (res.get("block") or {}).get("tool") or ""
                inp_repr = json.dumps(
                    (res.get("block") or {}).get("input") or {}, ensure_ascii=False
                )
                out_repr = json.dumps(res.get("result") or {}, ensure_ascii=False)
                record_tool(
                    root_p,
                    tname,
                    latency_ms=elapsed_ms / max(1, len(exec_result.get("results") or [])),
                    bytes_in=len(inp_repr),
                    bytes_out=len(out_repr),
                    status=res.get("status") or "ok",
                )
            context.update(exec_result.get("context") or {})

            # Classify errors / dispatch recovery once per turn execution.
            error_results = [r for r in exec_result["results"] if _classify_error(r)]
            needs_follow_up = False
            terminal = False
            if error_results:
                for r in error_results:
                    kind = _classify_error(r) or "tool_failed"
                    rec = ledger.escalate(kind)
                    dispatch = _dispatch_recovery(root_p, rec["action"], bus, current_mode)
                    if dispatch.get("new_mode"):
                        current_mode = dispatch["new_mode"]
                    if rec["action"] == "terminal_error":
                        terminal = True
                        stop_reason = "terminal_error"
                        break
                    if rec["action"] == "surface_user_decision":
                        stop_reason = "user_decision_required"
                        break
                    # retry_same / retry_with_budget / compact_then_retry / safe_mode_retry
                    if rec["action"] in (
                        "retry_same",
                        "retry_with_budget",
                        "compact_then_retry",
                        "safe_mode_retry",
                    ):
                        needs_follow_up = True

            if terminal:
                bus.emit("turn_end", "error", {"turn": turn_idx, "stop": "terminal_error"})
                bus.emit("query_end", "error", {"turns_completed": turn_idx, "stop": stop_reason})
                run_hooks(root_p, "post_query", {"stop": stop_reason, "turns": turn_idx})
                return {
                    "session_id": bus.session_id,
                    "event_log": str(bus.path),
                    "terminal_state": "recovery_exhausted",
                    "stop_reason": stop_reason,
                    "turn_results": turn_results,
                    "ledger": ledger.to_dict(),
                }
            if stop_reason == "user_decision_required":
                break
            if needs_follow_up and follow_up_count < DEFAULT_MAX_FOLLOW_UPS:
                follow_up_count += 1
                bus.emit("turn_follow_up", "ok", {"turn": turn_idx, "attempt": follow_up_count + 1})
                continue
            break

        response_repr = json.dumps(exec_result.get("results") or [], ensure_ascii=False)
        record_turn(root_p, turn_idx, prompt_text=prompt_repr, response_text=response_repr)
        turn_results.append(
            {"turn": turn_idx, "results": exec_result["results"], "follow_ups": follow_up_count}
        )

        if stop_reason == "user_decision_required":
            bus.emit("turn_end", "blocked", {"turn": turn_idx, "stop": stop_reason})
            break
        if turn.get("stop_reason") == "work_remaining":
            needs_follow_up = True
        bus.emit(
            "turn_end",
            "ok",
            {
                "turn": turn_idx,
                "needs_follow_up": needs_follow_up,
                "follow_ups": follow_up_count,
                "mode": current_mode,
            },
        )
    else:
        # Only when the loop completed without break
        stop_reason = "plan_exhausted"

    # Proactive compact at the end (Layer 3).
    compact_res = compact(root_p)
    bus.emit("compact_done", "ok", {"layers_run": [l["layer"] for l in compact_res["layers"]]})
    cost = ledger_summary(root_p)
    bus.emit(
        "cost_summary",
        "ok",
        {
            "turns": cost.get("turns"),
            "tool_calls": cost.get("tool_calls"),
            "tokens": cost.get("tokens"),
            "cost_usd": cost.get("cost_usd"),
        },
    )
    bus.emit("query_end", "ok", {"turns_completed": len(turn_results), "stop": stop_reason})
    run_hooks(root_p, "post_query", {"stop": stop_reason, "turns": len(turn_results)})
    return {
        "session_id": bus.session_id,
        "event_log": str(bus.path),
        "stop_reason": stop_reason,
        "turn_results": turn_results,
        "ledger": ledger.to_dict(),
        "cost": cost,
        "context": context,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Run a plan JSON through the query loop.")
    ap.add_argument("plan")
    ap.add_argument("--root", default=".")
    ap.add_argument("--mode", default="default")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    out = run_plan(plan, root=args.root, mode=args.mode)
    print(
        json.dumps(
            {
                "session_id": out["session_id"],
                "event_log": out["event_log"],
                "stop_reason": out["stop_reason"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
