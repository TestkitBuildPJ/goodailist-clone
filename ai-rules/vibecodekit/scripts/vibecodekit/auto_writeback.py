"""Opportunistic memory writeback (v0.11.0, audit round 6).

Wires ``memory_writeback.update()`` to ``session_start`` so CLAUDE.md
auto-maintained sections refresh themselves periodically without
requiring the user to remember running ``/vibe-memory writeback update``.

Design constraints
==================
- **Rate-limited**: never run more often than ``min_interval_seconds``
  (default 30 min) — recorded in ``.vibecode/auto_writeback.json``.
- **Best-effort**: any exception is swallowed so a malformed CLAUDE.md
  cannot brick session startup.
- **Opt-out**: if ``.vibecode/auto_writeback_disabled`` exists the
  refresh is skipped (escape hatch for users who manage CLAUDE.md by
  hand or commit it via PR review).

References:
- ``references/24-memory-governance.md`` — section ownership rules.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MIN_INTERVAL_SECONDS = 30 * 60  # 30 minutes
STATE_FILENAME = "auto_writeback.json"
DISABLE_MARKER = "auto_writeback_disabled"


@dataclass(frozen=True)
class RefreshDecision:
    """Outcome of :func:`try_refresh`.

    ``ran`` is true iff ``memory_writeback.update()`` actually executed
    (not skipped due to rate-limit / opt-out / missing CLAUDE.md).
    ``reason`` always carries a short machine-readable code.
    """

    ran: bool
    reason: str
    elapsed_s: float = 0.0
    sections_updated: tuple[str, ...] = ()


def _state_dir(repo_root: Path) -> Path:
    return repo_root / ".vibecode"


def _state_path(repo_root: Path) -> Path:
    return _state_dir(repo_root) / STATE_FILENAME


def _read_last_run(repo_root: Path) -> float:
    p = _state_path(repo_root)
    if not p.is_file():
        return 0.0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return float(data.get("last_run_ts", 0.0))
    except (OSError, ValueError, TypeError):
        return 0.0


def _write_last_run(
    repo_root: Path, ts: float, reason: str = "ok", sections: tuple[str, ...] = ()
) -> None:
    sd = _state_dir(repo_root)
    sd.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_run_ts": ts,
        "last_run_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        "last_reason": reason,
        "sections_updated": list(sections),
    }
    # Atomic write — auto_writeback may race with manual writeback runs.
    tmp = sd / (STATE_FILENAME + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, _state_path(repo_root))


def should_refresh(
    repo_root: Path,
    min_interval_seconds: int = DEFAULT_MIN_INTERVAL_SECONDS,
    *,
    now: float | None = None,
) -> bool:
    """Pure check — does NOT mutate state."""
    if (_state_dir(repo_root) / DISABLE_MARKER).exists():
        return False
    if now is None:
        now = time.time()
    last = _read_last_run(repo_root)
    return (now - last) >= float(min_interval_seconds)


def try_refresh(
    repo_root: os.PathLike[str] | str,
    min_interval_seconds: int = DEFAULT_MIN_INTERVAL_SECONDS,
    *,
    now: float | None = None,
    force: bool = False,
) -> RefreshDecision:
    """Run ``memory_writeback.update`` if rate-limit & opt-out allow.

    Always returns a :class:`RefreshDecision`; never raises.  Designed
    to be safe to call from ``session_start`` / ``post_tool_use`` hooks.
    """
    repo = Path(repo_root).resolve()
    if not (repo / "CLAUDE.md").is_file():
        return RefreshDecision(False, "no_claude_md")
    if (_state_dir(repo) / DISABLE_MARKER).exists() and not force:
        return RefreshDecision(False, "opted_out")
    if not force and not should_refresh(repo, min_interval_seconds, now=now):
        return RefreshDecision(False, "rate_limited")

    started = time.time() if now is None else now
    try:
        # Lazy import — keeps this module dependency-light for hooks.
        from . import memory_writeback as mw_mod

        wb = mw_mod.MemoryWriteback(repo)
        report = wb.update()
        sections = tuple(report.sections_updated) if hasattr(report, "sections_updated") else ()
        elapsed = time.time() - started
        _write_last_run(repo, started, "ok", sections)
        return RefreshDecision(True, "ok", elapsed, sections)
    except Exception as exc:  # noqa: BLE001 — best-effort, log via reason
        # Record the failed attempt so we don't hammer on a broken state.
        try:
            _write_last_run(repo, started, f"error: {type(exc).__name__}")
        except Exception:
            pass
        return RefreshDecision(False, f"error: {type(exc).__name__}")
