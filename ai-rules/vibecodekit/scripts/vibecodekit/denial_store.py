"""Denial tracking with consecutive / total thresholds and TTL.

Mirrors Claude Code's ``DenialTrackingState`` (Giải phẫu §5.8):

    DENIAL_LIMITS = {
        maxConsecutive: 3,
        maxTotal:      20,
    }

Plus a ``ttl_seconds`` (default 24h) so a one-off denial doesn't follow a
project forever.  ``record_success()`` resets *consecutive* but keeps *total*.

v0.8 — concurrency hardening.  Every mutation is wrapped in a
``fcntl``-style advisory lock on the file (``LOCK_EX``) with a
read-modify-write inside the critical section and an atomic
``os.replace`` to swap the file.  On Windows (no fcntl) we fall back to
``msvcrt.locking`` in a best-effort way.  This fixes the v0.7 race in
which eight concurrent ``ThreadPoolExecutor`` tool executions could
drop denials.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from vibecodekit._logging import get_logger
from vibecodekit._platform_lock import file_lock

_log = get_logger("vibecodekit.denial_store")

DEFAULT_MAX_CONSECUTIVE = 3
DEFAULT_MAX_TOTAL = 20
DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24h


def _key(action: str) -> str:
    return hashlib.sha256(action.strip().encode("utf-8")).hexdigest()[:16]


class DenialStore:
    def __init__(
        self,
        root: str | os.PathLike[str] = ".",
        max_consecutive: int = DEFAULT_MAX_CONSECUTIVE,
        max_total: int = DEFAULT_MAX_TOTAL,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / ".vibecode" / "runtime" / "denials.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_suffix(".lock")
        self.max_consecutive = max_consecutive
        self.max_total = max_total
        self.ttl_seconds = ttl_seconds
        # Evict expired under lock so concurrent instances agree on state.
        with self._locked():
            self._data = self._read()
            self._data.setdefault("_state", {"consecutive": 0, "total": 0})
            self._evict_expired_locked()
            self._write(self._data)
        self._state = self._data["_state"]

    # -------- Locked I/O --------
    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """Acquire an advisory exclusive lock on ``lock_path``.

        Uses ``fcntl.LOCK_EX`` on POSIX.  Creates the lock file on demand.
        Releases the lock when the context exits (even on exception).
        """
        fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with file_lock(fd):
                yield
        finally:
            os.close(fd)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        """Atomic write via temp file + ``os.replace``."""
        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=".denials.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp_name)
            raise

    def _evict_expired_locked(self) -> None:
        now = time.time()
        expired = [
            k
            for k, rec in self._data.items()
            if k != "_state"
            and isinstance(rec, dict)
            and (now - rec.get("last_ts", 0)) > self.ttl_seconds
        ]
        for k in expired:
            del self._data[k]

    # -------- API (all read-modify-write under the lock) --------
    def record_denial(self, action: str, reason: str) -> dict[str, Any]:
        with self._locked():
            self._data = self._read()
            state = self._data.setdefault("_state", {"consecutive": 0, "total": 0})
            k = _key(action)
            rec = self._data.get(k) or {"action": action, "count": 0, "reasons": []}
            rec["count"] = rec.get("count", 0) + 1
            rec["last_ts"] = time.time()
            rec.setdefault("reasons", []).append(reason)
            self._data[k] = rec
            state["consecutive"] = state.get("consecutive", 0) + 1
            state["total"] = state.get("total", 0) + 1
            self._write(self._data)
            self._state = state
            _log.debug(
                "denial_recorded",
                extra={
                    "key": k,
                    "count": rec["count"],
                    "consecutive": state["consecutive"],
                    "total": state["total"],
                },
            )
            return dict(rec)

    def record_success(self) -> None:
        with self._locked():
            self._data = self._read()
            state = self._data.setdefault("_state", {"consecutive": 0, "total": 0})
            state["consecutive"] = 0
            self._write(self._data)
            self._state = state

    def denied_before(self, action: str) -> dict[str, Any] | None:
        """Return the recorded entry only if it crosses the threshold (≥ 2 same cmd)."""
        with self._locked():
            self._data = self._read()
        k = _key(action)
        rec = self._data.get(k)
        if not rec or not isinstance(rec, dict):
            return None
        if rec.get("count", 0) < 2:
            return None
        if (time.time() - rec.get("last_ts", 0)) > self.ttl_seconds:
            return None
        return dict(rec)

    def should_fallback_to_user(self) -> bool:
        """Circuit breaker: too many denials → stop auto-denying and ask user."""
        with self._locked():
            self._data = self._read()
            state = self._data.get("_state", {})
        return bool(
            state.get("consecutive", 0) >= self.max_consecutive
            or state.get("total", 0) >= self.max_total
        )

    def state(self) -> dict[str, Any]:
        with self._locked():
            self._data = self._read()
        return dict(self._data.get("_state", {}))

    def clear(self) -> None:
        with self._locked():
            self._data = {"_state": {"consecutive": 0, "total": 0}}
            self._state = self._data["_state"]
            self._write(self._data)
