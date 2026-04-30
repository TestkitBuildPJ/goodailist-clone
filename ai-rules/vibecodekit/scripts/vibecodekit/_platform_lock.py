"""Cross-platform advisory file locking helper.

Uses ``fcntl.flock`` on POSIX and ``msvcrt.locking`` on Windows.  If neither
is available (extremely rare), degrades gracefully to a NO-OP lock — callers
should assume "best-effort single-process" semantics in that case.

Usage::

    from vibecodekit._platform_lock import file_lock

    with file_lock(fd):
        ...  # exclusive region

``fd`` must be a file descriptor opened with write-access (e.g. from
``os.open(path, os.O_RDWR | os.O_CREAT)``).
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator

try:  # POSIX
    import fcntl  # type: ignore

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows
    _HAS_FCNTL = False

try:  # Windows
    import msvcrt  # type: ignore

    _HAS_MSVCRT = True
except ImportError:  # pragma: no cover — POSIX
    _HAS_MSVCRT = False

# Lock region size for msvcrt.locking — we lock the first byte of the file,
# which is enough for advisory mutual exclusion.
_MSVCRT_LOCK_SIZE = 1


@contextlib.contextmanager
def file_lock(fd: int) -> Iterator[None]:
    """Acquire an exclusive advisory lock on ``fd`` for the duration of the
    context.  Cross-platform: uses ``fcntl`` on POSIX, ``msvcrt`` on Windows,
    NO-OP if neither is available.
    """
    acquired_posix = False
    acquired_win = False
    if _HAS_FCNTL:
        fcntl.flock(fd, fcntl.LOCK_EX)
        acquired_posix = True
    elif _HAS_MSVCRT:
        # ``msvcrt.locking`` locks starting at the current file pointer.
        # Ensure we lock from offset 0.
        try:
            os.lseek(fd, 0, os.SEEK_SET)
        except OSError:
            pass
        # LK_LOCK blocks until lock is acquired (up to ~10 seconds by default
        # on some systems; we retry once more to be safe).
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK, _MSVCRT_LOCK_SIZE)
            acquired_win = True
        except OSError:
            # Give up after one retry; caller degrades to NO-OP semantics
            # unless ``VIBECODE_STRICT_LOCK=1`` is set, in which case surface
            # the failure to the caller rather than silently racing.
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, _MSVCRT_LOCK_SIZE)
                acquired_win = True
            except OSError as e:
                if os.environ.get("VIBECODE_STRICT_LOCK") == "1":
                    raise RuntimeError(f"file_lock: msvcrt.locking failed after retry: {e}") from e
    try:
        yield
    finally:
        if acquired_posix:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        elif acquired_win:
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, _MSVCRT_LOCK_SIZE)
            except OSError:
                pass


def has_real_locking() -> bool:
    """Return True iff we have a real platform lock (fcntl or msvcrt)."""
    return _HAS_FCNTL or _HAS_MSVCRT
