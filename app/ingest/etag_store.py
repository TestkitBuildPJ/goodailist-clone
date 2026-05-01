"""In-memory ETag cache.

Phase B: process-local — cleared on container restart, which means the first
post-restart cron tick re-fetches all repos.  Acceptable cost: 30 calls.

Persisting the ETag store is deferred to a future phase if the restart cost
becomes meaningful.
"""

from __future__ import annotations

from threading import Lock


class EtagStore:
    """Thread-safe ``(owner, repo) → etag`` map."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], str] = {}
        self._lock = Lock()

    def get(self, owner: str, repo: str) -> str | None:
        """Return the cached ETag for ``owner/repo`` or ``None`` if absent."""
        with self._lock:
            return self._data.get((owner, repo))

    def set(self, owner: str, repo: str, etag: str) -> None:
        """Store an ETag.  Empty strings are treated as "no etag" and ignored."""
        if not etag:
            return
        with self._lock:
            self._data[(owner, repo)] = etag

    def clear(self) -> None:
        """Drop all cached ETags (used by tests)."""
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
