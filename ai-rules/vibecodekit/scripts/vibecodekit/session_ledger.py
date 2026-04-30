"""session_ledger — append-only JSONL of gates run in the current ship cycle.

Used by :mod:`vibecodekit.team_mode` to verify required gates have run
before ``/vck-ship`` allows a merge.

Lifecycle:

- Slash commands like ``/vck-review`` and ``/vck-qa-only`` append a row
  here when they finish (via ``python -m vibecodekit.team_mode record``).
- ``/vck-ship`` Bước 0 reads it (via ``team_mode check``) and refuses
  to proceed if any gate from ``.vibecode/team.json`` is missing.
- ``/vck-ship`` Bước 7 calls ``team_mode clear`` after the PR is open,
  resetting the ledger for the next ship cycle.

The ledger is **append-only JSONL** so concurrent appenders do not
corrupt each other (POSIX guarantees small-write atomicity for the
``a`` mode on a regular file system).  Reads tolerate truncated or
malformed lines.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

__all__ = [
    "LEDGER_PATH",
    "ledger_path",
    "record_gate",
    "gates_run",
    "clear",
]

LEDGER_PATH = ".vibecode/session_ledger.jsonl"


def ledger_path(root: Path | None = None) -> Path:
    return Path(root or Path.cwd()) / LEDGER_PATH


def record_gate(name: str, root: Path | None = None, extra: dict | None = None) -> dict:
    """Append a ``{gate, ts, ...}`` row to the ledger.  Returns the row."""
    p = ledger_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry: dict = {"gate": str(name), "ts": time.time()}
    if extra:
        # Drop any keys that would shadow our fixed schema.
        for k, v in extra.items():
            if k in ("gate", "ts"):
                continue
            entry[k] = v
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def gates_run(root: Path | None = None) -> list[str]:
    """Return list of gate names recorded so far (preserves duplicates)."""
    p = ledger_path(root)
    if not p.is_file():
        return []
    out: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            # Tolerate corrupt rows — better to miss a gate than crash.
            continue
        g = d.get("gate")
        if isinstance(g, str) and g:
            out.append(g)
    return out


def clear(root: Path | None = None) -> None:
    """Delete the ledger file (no-op if missing)."""
    p = ledger_path(root)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        # Permission / read-only filesystem — surface so caller knows.
        raise
