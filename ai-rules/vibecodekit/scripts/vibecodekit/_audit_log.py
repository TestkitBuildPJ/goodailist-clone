"""Rate-capped audit log for permission denials (PR4).

Ghi entry mỗi lần `permission_engine.decide()` ra quyết định strict-deny
(9-pattern mới + existing blocked) vào file append-only JSONL:

    ~/.vibecode/security/attempts.jsonl

Format mỗi entry (1 dòng JSON):

    {"ts": "2026-04-29T17:30:00Z",
     "decision": "deny",
     "rule_id": "R-CHMOD-WORLD-ROOT-001",
     "cmd_hash": "sha256:abc...",
     "mode": "default",
     "severity": "high"}

**Quan trọng:** chỉ ghi `cmd_hash` (sha256 prefix 32 char) — KHÔNG ghi
`cmd` plaintext để tránh leak credential nếu command chứa env var /
API token.

Rate cap: sliding window 60 giây, tối đa 60 entry/phút.  Vượt → drop
entry + tăng counter `dropped_count` trong sidecar `attempts.meta.json`.
Meta rotate hourly: `hour_key` field reset về đầu giờ → `dropped_count`
mới reset về 0.

Override path: env `VIBECODE_AUDIT_LOG_DIR` (tiện test + fallback tới
`tempfile.gettempdir()` khi `~` không writable trong CI sandbox).

Invariants:
* Thread/process safe qua `vibecodekit._platform_lock.file_lock`.
* Stdlib only (`hashlib`, `json`, `os`, `pathlib`, `tempfile`, `time`).
* Failure mode: mọi exception I/O → silent no-op (audit là best-effort;
  không được chặn / crash classifier pipeline).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections import deque
from pathlib import Path

from ._logging import get_logger
from ._platform_lock import file_lock

_log = get_logger("vibecodekit._audit_log")

# Sliding-window configuration.
_WINDOW_SECONDS = 60
_MAX_PER_WINDOW = 60

# In-process sliding window timestamps (not cross-process — cross-process
# rate limiting is a best-effort overlay documented as single-agent scope).
_window: deque[float] = deque()


def _audit_dir() -> Path:
    """Resolve audit directory (respect env override + tempfile fallback).

    Path alignment: ``~/.vibecode/security/`` (cùng dotdir với
    ``denial_store.py``, ``memory_hierarchy.py``, ``learnings.py``,
    ``methodology.py``).  Đồng thuận với CONTRIBUTING.md rule
    "No mutable global state outside ``~/.vibecode/`` and
    ``.vibecode/``" — tránh split security state giữa 2 dotdir.
    """
    override = os.environ.get("VIBECODE_AUDIT_LOG_DIR")
    if override:
        return Path(override)
    home = os.environ.get("HOME") or os.path.expanduser("~")
    if home and home != "~" and os.access(home, os.W_OK):
        return Path(home) / ".vibecode" / "security"
    # Sandbox / CI without writable HOME → tempdir fallback.
    return Path(tempfile.gettempdir()) / "vibecode-security"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def cmd_hash(cmd: str) -> str:
    """Stable sha256 prefix hash of the command string."""
    h = hashlib.sha256(cmd.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{h[:32]}"


def _hour_key(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H", time.gmtime(ts))


def _within_rate_limit(now: float) -> bool:
    """Drop oldest timestamps outside the 60s window; accept if len < cap."""
    cutoff = now - _WINDOW_SECONDS
    while _window and _window[0] < cutoff:
        _window.popleft()
    if len(_window) >= _MAX_PER_WINDOW:
        return False
    _window.append(now)
    return True


def _bump_meta_counter_locked(meta_path: Path, now: float) -> None:
    """Increment dropped_count; rotate hour_key when crossing hour boundary."""
    hk = _hour_key(now)
    current: dict[str, object] = {}
    if meta_path.exists():
        try:
            loaded = json.loads(meta_path.read_text(encoding="utf-8") or "{}")
            if isinstance(loaded, dict):
                current = loaded
        except json.JSONDecodeError:
            current = {}
    if current.get("hour_key") != hk:
        current = {"hour_key": hk, "dropped_count": 0}
    raw_count = current.get("dropped_count", 0)
    prev = raw_count if isinstance(raw_count, int) else 0
    current["dropped_count"] = prev + 1
    meta_path.write_text(
        json.dumps(current, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record_attempt(
    *,
    decision: str,
    rule_id: str,
    cmd: str,
    mode: str,
    severity: str,
    now: float | None = None,
) -> bool:
    """Append 1 entry to attempts.jsonl if inside rate window, else drop.

    Returns True if entry was written; False if dropped (rate-cap) or
    on I/O error.  Never raises.
    """
    try:
        ts = time.time() if now is None else now
        directory = _audit_dir()
        _ensure_dir(directory)
        log_path = directory / "attempts.jsonl"
        meta_path = directory / "attempts.meta.json"
        lock_path = directory / "attempts.lock"

        fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with file_lock(fd):
                if not _within_rate_limit(ts):
                    _bump_meta_counter_locked(meta_path, ts)
                    return False
                entry = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                    "decision": decision,
                    "rule_id": rule_id,
                    "cmd_hash": cmd_hash(cmd),
                    "mode": mode,
                    "severity": severity,
                }
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                return True
        finally:
            os.close(fd)
    except Exception as exc:  # noqa: BLE001 — best-effort logging
        _log.debug("audit_log_error", extra={"error": str(exc)})
        return False


def reset_window_for_tests() -> None:
    """Clear in-memory sliding window (test isolation)."""
    _window.clear()
