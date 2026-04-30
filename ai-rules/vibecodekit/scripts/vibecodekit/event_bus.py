"""Single append-only JSONL event bus for the v0.7 runtime.

Each session writes one file:  ``.vibecode/runtime/<session>.events.jsonl``

Event record schema::

    {
      "ts":         float,   # seconds since epoch
      "session_id": str,     # e.g. "vibe-20260425-130455-a1b2"
      "turn":       int,     # 0 before loop starts, then 1, 2, ...
      "event":      str,     # e.g. "turn_start", "tool_result"
      "status":     str,     # "ok" | "error" | "deny" | "blocked"
      "schema":     "vibe.event/1",
      "payload":    dict,
    }

The bus is deliberately simple (no rotation, no network sink) — see
references/01-async-generator-loop.md for the rationale.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "vibe.event/1"


class EventBus:
    def __init__(self, root: str | os.PathLike = ".", session_id: str | None = None) -> None:
        self.root = Path(root).resolve()
        self.session_id = session_id or self._new_session_id()
        self.dir = self.root / ".vibecode" / "runtime"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{self.session_id}.events.jsonl"
        self._turn = 0

    @staticmethod
    def _new_session_id() -> str:
        return "vibe-" + time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)

    def set_turn(self, n: int) -> None:
        self._turn = int(n)

    def emit(
        self, event: str, status: str = "ok", payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        rec = {
            "ts": time.time(),
            "session_id": self.session_id,
            "turn": self._turn,
            "event": event,
            "status": status,
            "schema": SCHEMA,
            "payload": payload or {},
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # filesystems without fsync (tmpfs in some sandboxes) shouldn't crash the run
                pass
        return rec

    def read_all(self) -> Iterable[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
