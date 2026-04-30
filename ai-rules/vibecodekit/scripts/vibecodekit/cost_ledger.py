"""Token / cost accounting ledger — Giải phẫu §12.4 (Telemetry architecture).

Tracks per-turn and per-session resource usage so operators can see:

* tokens (input / output / cached) approximated from text length;
* tool-call counts and latencies;
* denials and recovery events;
* aggregate cost estimated via ``COST_TABLE`` (tokens-per-$).

Ledger on disk::

    .vibecode/runtime/ledger.jsonl   # one JSON line per event
    .vibecode/runtime/ledger-summary.json   # rolled-up totals

Public surface (used by query_loop + dashboard)::

    record_turn(root, turn_no, stats)
    record_tool(root, tool_name, latency_ms, bytes_in, bytes_out, status)
    record_event(root, event)            # generic
    summary(root) -> dict                # totals
    reset(root) -> None

All writes are atomic line-appends — no locking needed because append is
itself atomic on POSIX for payloads < ``PIPE_BUF`` (4096 bytes).

References:
- ``references/28-cost-ledger.md``
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Rough per-million-token prices (USD) — illustrative defaults; the real
# numbers are configurable via env vars.
COST_TABLE: dict[str, dict[str, float]] = {
    "default": {"input": 3.0, "output": 15.0, "cached": 0.30},
    "sonnet": {"input": 3.0, "output": 15.0, "cached": 0.30},
    "haiku": {"input": 1.0, "output": 5.0, "cached": 0.10},
    "opus": {"input": 15.0, "output": 75.0, "cached": 1.50},
}


def _ledger_path(root: Path) -> Path:
    p = root / ".vibecode" / "runtime" / "ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _summary_path(root: Path) -> Path:
    return root / ".vibecode" / "runtime" / "ledger-summary.json"


def _approx_tokens(text: str) -> int:
    """Very rough 4-chars-per-token heuristic.  Real implementations should
    use tiktoken — v0.8 avoids the dependency."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def record_event(root: str | os.PathLike, event: dict[str, Any]) -> None:
    root_p = Path(root).resolve()
    event = dict(event)
    event.setdefault("ts", time.time())
    line = json.dumps(event, ensure_ascii=False)
    with _ledger_path(root_p).open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def record_tool(
    root: str | os.PathLike,
    tool: str,
    *,
    latency_ms: float,
    bytes_in: int,
    bytes_out: int,
    status: str = "ok",
) -> None:
    record_event(
        root,
        {
            "kind": "tool",
            "tool": tool,
            "latency_ms": round(latency_ms, 2),
            "bytes_in": bytes_in,
            "bytes_out": bytes_out,
            "status": status,
        },
    )


def record_turn(
    root: str | os.PathLike,
    turn_no: int,
    prompt_text: str = "",
    response_text: str = "",
    *,
    model: str = "default",
) -> dict[str, int]:
    prompt_tokens = _approx_tokens(prompt_text)
    completion_tokens = _approx_tokens(response_text)
    record_event(
        root,
        {
            "kind": "turn",
            "turn_no": turn_no,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def summary(root: str | os.PathLike) -> dict[str, Any]:
    root_p = Path(root).resolve()
    p = _ledger_path(root_p)
    if not p.exists():
        return {"turns": 0, "tool_calls": 0, "tokens": 0, "cost_usd": 0.0}
    turns = 0
    tool_calls = 0
    tokens_in = 0
    tokens_out = 0
    tokens_cached = 0
    tool_stats: dict[str, dict[str, Any]] = {}
    model_default = "default"
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") == "turn":
            turns += 1
            tokens_in += int(rec.get("prompt_tokens", 0))
            tokens_out += int(rec.get("completion_tokens", 0))
            tokens_cached += int(rec.get("cached_tokens", 0))
            model_default = rec.get("model") or model_default
        elif rec.get("kind") == "tool":
            tool_calls += 1
            name = rec.get("tool", "<unknown>")
            st = tool_stats.setdefault(
                name, {"count": 0, "errors": 0, "latency_ms": 0.0, "bytes_in": 0, "bytes_out": 0}
            )
            st["count"] += 1
            if rec.get("status") not in (None, "ok"):
                st["errors"] += 1
            st["latency_ms"] += float(rec.get("latency_ms", 0))
            st["bytes_in"] += int(rec.get("bytes_in", 0))
            st["bytes_out"] += int(rec.get("bytes_out", 0))
    prices = COST_TABLE.get(model_default, COST_TABLE["default"])
    cost_usd = (
        tokens_in * prices["input"] / 1_000_000
        + tokens_out * prices["output"] / 1_000_000
        + tokens_cached * prices["cached"] / 1_000_000
    )
    out = {
        "turns": turns,
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_cached": tokens_cached,
        "tokens": tokens_in + tokens_out + tokens_cached,
        "cost_usd": round(cost_usd, 6),
        "model_default": model_default,
        "per_tool": tool_stats,
    }
    _summary_path(root_p).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def reset(root: str | os.PathLike) -> None:
    root_p = Path(root).resolve()
    for p in (_ledger_path(root_p), _summary_path(root_p)):
        if p.exists():
            p.unlink()
