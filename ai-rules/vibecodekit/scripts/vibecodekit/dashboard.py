"""Runtime dashboard — summarises events for /vibe-dashboard.

Reads every ``.events.jsonl`` under ``.vibecode/runtime`` and prints a
human-readable summary: turn counts, tool tallies, permission decisions,
compaction layers run, recovery actions.  Used in both CI (pytest) and
interactive CLI.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

from ._logging import get_logger

_log = get_logger("vibecodekit.dashboard")


def summarise(root: str | os.PathLike = ".") -> dict[str, Any]:
    root = Path(root).resolve()
    rt = root / ".vibecode" / "runtime"
    events: list[dict[str, Any]] = []
    for f in sorted(rt.glob("*.events.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            continue
    event_counts = Counter(e.get("event") for e in events)
    tool_counts = Counter()
    permission_counts = Counter()
    recovery_counts = Counter()
    errors: list[dict[str, Any]] = []
    last_session = None
    for e in events:
        last_session = e.get("session_id")
        if e.get("event") == "tool_result":
            block = (e.get("payload") or {}).get("block") or {}
            tool_counts[block.get("tool")] += 1
            if e.get("status") in ("error", "deny", "blocked"):
                errors.append(
                    {"turn": e.get("turn"), "tool": block.get("tool"), "status": e.get("status")}
                )
        if (e.get("event") or "").startswith("recovery_"):
            recovery_counts[e["event"]] += 1
    for f in (rt).glob("denials.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            for k, v in d.items():
                if k == "_state":
                    permission_counts["denials_state"] = v
                else:
                    permission_counts["denied_actions"] = (
                        permission_counts.get("denied_actions", 0) + 1
                    )
        except Exception:
            pass
    return {
        "root": str(root),
        "session": last_session,
        "event_total": len(events),
        "event_counts": dict(event_counts),
        "tool_counts": dict(tool_counts),
        "recovery_counts": dict(recovery_counts),
        "permission": dict(permission_counts),
        "errors": errors[:50],
    }


def _main() -> None:
    ap = argparse.ArgumentParser(description="Summarise runtime events.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    s = summarise(args.root)
    if args.json:
        _log.info("dashboard_summary_json", extra={"summary": s})
        return
    _log.info("dashboard_root", extra={"root": s["root"]})
    _log.info(
        "dashboard_session",
        extra={"session": s["session"], "event_total": s["event_total"]},
    )
    _log.info("dashboard_tool_counts", extra={"tool_counts": s["tool_counts"]})
    _log.info("dashboard_event_counts", extra={"event_counts": s["event_counts"]})
    if s["recovery_counts"]:
        _log.info(
            "dashboard_recovery_counts",
            extra={"recovery_counts": s["recovery_counts"]},
        )
    if s["errors"]:
        _log.info("dashboard_errors", extra={"errors": s["errors"]})


if __name__ == "__main__":
    _main()
