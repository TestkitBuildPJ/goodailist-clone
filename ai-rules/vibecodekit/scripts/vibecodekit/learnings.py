"""learnings — per-project JSONL learning store.

A lightweight, stdlib-only append-log that captures a lesson (text,
tags, author, scope) whenever the operator runs ``/vck-learn``.
``load`` replays the store on session start so the host can inject
prior learnings into the system prompt.

Scope hierarchy matches :mod:`memory_hierarchy`::

  user    — ``~/.vibecode/learnings.jsonl``         (cross-project)
  project — ``.vibecode/learnings.jsonl``           (repo-local)
  team    — ``.vibecode/learnings.team.jsonl``      (committed)

Writes are atomic (tmp + os.replace) and fcntl-locked — two Devin
sessions writing to the same store will not corrupt the log.  This
reuses :mod:`_platform_lock` so Windows hosts fall through to a
no-op lock gracefully.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import _platform_lock
from ._logging import get_logger

_log = get_logger("vibecodekit.learnings")

__all__ = [
    "Learning",
    "LearningStore",
    "user_store",
    "project_store",
    "team_store",
    "load_all",
    "load_recent",
    "recent_for_prompt",
    "capture",
]

SCOPES = ("user", "project", "team")


@dataclass(frozen=True)
class Learning:
    """One learning entry."""

    text: str
    scope: str = "project"
    tags: Sequence[str] = field(default_factory=tuple)
    author: str = ""
    captured_ts: float = 0.0

    def as_dict(self) -> dict:
        d = asdict(self)
        d["tags"] = list(self.tags)
        return d

    @classmethod
    def from_dict(cls, raw: dict) -> Learning:
        return cls(
            text=str(raw.get("text", "")),
            scope=str(raw.get("scope", "project")),
            tags=tuple(raw.get("tags") or ()),
            author=str(raw.get("author", "")),
            captured_ts=float(raw.get("captured_ts") or 0.0),
        )


class LearningStore:
    """Append-only JSONL store for a single scope."""

    def __init__(self, path: Path | str, scope: str = "project") -> None:
        if scope not in SCOPES:
            raise ValueError(f"bad scope {scope!r}; want one of {SCOPES}")
        self._path = Path(path)
        self._scope = scope

    @property
    def path(self) -> Path:
        return self._path

    @property
    def scope(self) -> str:
        return self._scope

    def append(self, learning: Learning) -> Learning:
        """Append one learning; returns the persisted record (with timestamp filled)."""
        if learning.captured_ts == 0.0:
            learning = Learning(
                text=learning.text,
                scope=self._scope,
                tags=tuple(learning.tags),
                author=learning.author,
                captured_ts=time.time(),
            )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic append under fcntl lock.
        lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        lock_fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            with _platform_lock.file_lock(lock_fd):
                line = json.dumps(learning.as_dict(), ensure_ascii=False) + "\n"
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        pass
        finally:
            os.close(lock_fd)
        return learning

    def load(self) -> list[Learning]:
        if not self._path.is_file():
            return []
        out: list[Learning] = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(Learning.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
        return out

    def clear(self) -> None:
        """Delete the log.  Used by tests only."""
        if self._path.exists():
            self._path.unlink()


# ---------------------------------------------------------------------------
# Scope-specific helpers
# ---------------------------------------------------------------------------


def user_store(home: Path | None = None) -> LearningStore:
    home = home or Path(os.environ.get("VIBECODE_HOME") or Path.home() / ".vibecode")
    return LearningStore(home / "learnings.jsonl", scope="user")


def project_store(root: Path | None = None) -> LearningStore:
    root = Path(root or Path.cwd())
    return LearningStore(root / ".vibecode" / "learnings.jsonl", scope="project")


def team_store(root: Path | None = None) -> LearningStore:
    root = Path(root or Path.cwd())
    return LearningStore(root / ".vibecode" / "learnings.team.jsonl", scope="team")


def load_all(root: Path | None = None, home: Path | None = None) -> list[Learning]:
    """Merge user + team + project learnings (project last, overrides nothing)."""
    out: list[Learning] = []
    out.extend(user_store(home).load())
    out.extend(team_store(root).load())
    out.extend(project_store(root).load())
    return out


def load_recent(
    limit: int = 10,
    root: Path | None = None,
    home: Path | None = None,
    scopes: Iterable[str] | None = None,
) -> list[Learning]:
    """Return the ``limit`` most-recent learnings, optionally scope-filtered.

    Sorted by ``captured_ts`` descending so the freshest item comes
    first.  Used by the ``session_start`` hook to inject prior context
    into the host LLM (auto-on by default; opt-out with
    ``VIBECODE_LEARNINGS_INJECT=0``).

    ``scopes`` (added v0.15.3) restricts the result to a subset of the
    canonical scope tuple ``("user", "project", "team")``.  When
    ``None`` (default) all scopes are included, preserving the v0.15.0
    behaviour.  Unknown scope labels are silently dropped.
    """
    if limit <= 0:
        return []
    items = load_all(root=root, home=home)
    if scopes is not None:
        allowed = {s for s in scopes if s in SCOPES}
        items = [l for l in items if l.scope in allowed]
    items.sort(key=lambda l: l.captured_ts, reverse=True)
    return items[:limit]


def recent_for_prompt(
    limit: int = 10,
    scopes: Iterable[str] | None = None,
    root: Path | None = None,
    home: Path | None = None,
) -> str:
    """Format the most-recent learnings as a markdown addendum.

    Returns a markdown snippet ready to inject into the host LLM's
    system-prompt addendum at session start.  Empty string when no
    learnings exist (caller can skip injection cleanly).

    The format is intentionally compact — one bullet per learning,
    prefixed with ``[scope]`` and a tags inline so the LLM has just
    enough context to reference prior decisions.  Added in v0.15.3
    to close the markdown-addendum gap from the v0.15.0 plan T3.
    """
    items = load_recent(limit=limit, scopes=scopes, root=root, home=home)
    if not items:
        return ""
    lines: list[str] = ["## Prior learnings (auto-injected at session start)"]
    for l in items:
        tags = f" `#{' #'.join(l.tags)}`" if l.tags else ""
        text = l.text.strip().replace("\n", " ")
        lines.append(f"- **[{l.scope}]**{tags} {text}")
    return "\n".join(lines)


def capture(
    text: str,
    scope: str = "project",
    tags: Sequence[str] = (),
    author: str = "",
    root: Path | None = None,
    home: Path | None = None,
) -> Learning:
    """Convenience: append to the right store given a scope."""
    store: LearningStore
    if scope == "user":
        store = user_store(home)
    elif scope == "team":
        store = team_store(root)
    else:
        store = project_store(root)
    return store.append(Learning(text=text, scope=scope, tags=tuple(tags), author=author))


# ---------------------------------------------------------------------------
# CLI helper: vibe learnings {capture|list|clear}
# ---------------------------------------------------------------------------


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Per-project learnings store")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="Append one learning.")
    cap.add_argument("--scope", default="project", choices=SCOPES)
    cap.add_argument("--tag", action="append", default=[])
    cap.add_argument("--author", default="")
    cap.add_argument("text", nargs="+")

    lst = sub.add_parser("list", help="List merged learnings.")
    lst.add_argument("--scope", default=None, choices=SCOPES)
    lst.add_argument("--json", action="store_true")

    sub.add_parser("clear", help="Clear project store (not user/team).")

    args = ap.parse_args(argv)

    if args.cmd == "capture":
        rec = capture(
            " ".join(args.text),
            scope=args.scope,
            tags=args.tag,
            author=args.author,
        )
        _log.info("learning_captured", extra={"record": rec.as_dict()})
        return 0
    if args.cmd == "list":
        if args.scope == "user":
            items = user_store().load()
        elif args.scope == "team":
            items = team_store().load()
        elif args.scope == "project":
            items = project_store().load()
        else:
            items = load_all()
        if args.json:
            _log.info(
                "learnings_list_json",
                extra={"items": [i.as_dict() for i in items]},
            )
        else:
            formatted = [
                {
                    "ts": time.strftime("%Y-%m-%d", time.localtime(it.captured_ts)),
                    "scope": it.scope,
                    "text": it.text,
                }
                for it in items
            ]
            _log.info("learnings_list", extra={"items": formatted})
        return 0
    if args.cmd == "clear":
        project_store().clear()
        _log.info("learnings_cleared", extra={"scope": "project"})
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
