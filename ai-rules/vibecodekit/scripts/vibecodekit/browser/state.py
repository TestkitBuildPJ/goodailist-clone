"""Atomic state file for the browser daemon — port / pid / idle / cookie path.

The state file lives at ``~/.vibecode/browser.json`` (mode 0o600). It is the
single source of truth that links the CLI client to a running daemon. All
writes are atomic (tmp + ``os.replace``) and protected by an advisory file
lock so two CLIs racing to spawn a daemon cannot corrupt the file.

Port-selection policy: random port in ``[10_000, 60_000)``; on collision
retry up to 5 times before giving up.

This module is stdlib-only — it does NOT import playwright / fastapi.

Probes covered
--------------
#54 — state file 0o600 + atomic write.
#55 — daemon idle-timeout default 30 minutes.
#57 — cookie path persists across reads.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import json
import os
import random
import socket
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Default idle timeout (seconds) — daemon shuts down after this many
# seconds of inactivity.  Probe #55 verifies this default is exactly 30
# minutes.
DEFAULT_IDLE_TIMEOUT_SECONDS: int = 30 * 60

# Inclusive lower / exclusive upper bounds for daemon TCP port.
PORT_RANGE: tuple[int, int] = (10_000, 60_000)

# Maximum number of port-collision retries before giving up.
PORT_RETRY_BUDGET: int = 5


def state_path(home: Path | None = None) -> Path:
    """Return the canonical state file path under ``$HOME``."""
    base = Path(home) if home is not None else Path.home()
    return base / ".vibecode" / "browser.json"


@dataclass
class BrowserState:
    """Serialisable state of a running browser daemon."""

    pid: int = 0
    port: int = 0
    started_ts: float = 0.0
    last_activity_ts: float = 0.0
    idle_timeout_seconds: int = DEFAULT_IDLE_TIMEOUT_SECONDS
    cookie_path: str = ""
    protocol_version: str = "1.0.0"
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BrowserState:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known}
        extra = {k: v for k, v in data.items() if k not in known}
        if extra:
            existing = kwargs.get("extra", {})
            existing.update(extra)
            kwargs["extra"] = existing
        return cls(**kwargs)


def _ensure_dir(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def write_state(state: BrowserState, *, path: Path | None = None) -> Path:
    """Atomically write ``state`` to ``path`` (defaults to ``state_path()``).

    Mode is forced to 0o600 (owner read/write only).  The function uses
    a tmp file in the same directory + ``os.replace`` so a crash at any
    point leaves either the previous content or the new content — never
    a half-written file.  Probe #54 verifies the resulting permissions.
    """
    target = path or state_path()
    _ensure_dir(target)
    fd, tmp = tempfile.mkstemp(prefix=".browser.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        # Force the canonical 0o600 mode regardless of umask.
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    return target


def read_state(*, path: Path | None = None) -> BrowserState | None:
    """Return the current state, or ``None`` if the file is missing/corrupt."""
    target = path or state_path()
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return BrowserState.from_dict(data)


def clear_state(*, path: Path | None = None) -> bool:
    """Remove the state file. Returns True if a file was removed."""
    target = path or state_path()
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False


@contextlib.contextmanager
def state_lock(path: Path | None = None):
    """Hold an advisory file lock on the state file.

    Used to serialise read-modify-write cycles (e.g. CLI checking whether
    a daemon is alive and spawning one if not).
    """
    target = path or state_path()
    _ensure_dir(target)
    lock_path = target.with_suffix(target.suffix + ".lock")
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _is_port_free(port: int, *, host: str = "127.0.0.1") -> bool:
    """Return True iff ``port`` is currently bindable on ``host``."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            s.bind((host, port))
        except OSError as e:
            if e.errno in (errno.EADDRINUSE, errno.EACCES):
                return False
            raise
        return True
    finally:
        s.close()


def select_port(
    rng: random.Random | None = None, *, host: str = "127.0.0.1", budget: int = PORT_RETRY_BUDGET
) -> int:
    """Return a free TCP port in :data:`PORT_RANGE`.

    Tries up to ``budget`` random candidates; raises ``RuntimeError`` if
    every one is busy (extremely unlikely but possible on heavily loaded
    machines).
    """
    rnd = rng or random.Random()
    low, high = PORT_RANGE
    for _ in range(max(1, budget)):
        candidate = rnd.randrange(low, high)
        if _is_port_free(candidate, host=host):
            return candidate
    raise RuntimeError(f"could not find a free port in [{low}, {high}) after {budget} tries")


def is_pid_alive(pid: int) -> bool:
    """Return True iff ``pid`` is a live process in this PID namespace."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it — still "alive" for our purposes.
        return True
    return True


def is_idle_expired(state: BrowserState, *, now: float | None = None) -> bool:
    """Return True iff the daemon has been idle past its timeout."""
    t = time.time() if now is None else now
    if state.idle_timeout_seconds <= 0:
        return False
    if state.last_activity_ts <= 0:
        return False
    return (t - state.last_activity_ts) >= state.idle_timeout_seconds


def touch_state(*, path: Path | None = None, now: float | None = None) -> BrowserState | None:
    """Bump ``last_activity_ts`` on the existing state, atomically.

    Returns the updated state, or ``None`` if there is no current state
    file (no daemon running).
    """
    with state_lock(path):
        state = read_state(path=path)
        if state is None:
            return None
        state.last_activity_ts = time.time() if now is None else now
        write_state(state, path=path)
        return state


__all__ = [
    "DEFAULT_IDLE_TIMEOUT_SECONDS",
    "PORT_RANGE",
    "PORT_RETRY_BUDGET",
    "BrowserState",
    "state_path",
    "write_state",
    "read_state",
    "clear_state",
    "state_lock",
    "select_port",
    "is_pid_alive",
    "is_idle_expired",
    "touch_state",
]
