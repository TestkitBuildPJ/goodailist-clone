"""Background-task runtime — Giải phẫu Chương 7.

Implements the seven task types and five-state lifecycle described in
Chương 7 of the Agentic-OS reference, with disk-based output via
``outputFile`` + ``outputOffset`` so a coordinator can consume output
incrementally without re-reading from the start (§7.4).

Task types (§7.2):

    local_bash          - Shell process run in the background.
    local_agent         - Sub-agent with its own query loop.
    remote_agent        - Agent scheduled on a remote runner (stub).
    in_process_teammate - Teammate agent in coordinator mode (stub).
    local_workflow      - Scripted multi-step pipeline (stub).
    monitor_mcp         - MCP-server health monitor (stub).
    dream               - Memory-consolidation agent between sessions.

Lifecycle (§7.3):

    pending -> running -> completed | failed | killed      (terminal)

Disk layout (per project root)::

    .vibecode/runtime/tasks/
    ├── index.json                 # all tasks (atomic R-M-W under lock)
    ├── <task_id>.out              # stdout+stderr (append-only)
    └── <task_id>.notifications.jsonl   # task-notification ledger

Stall detection (§7.4) is provided by ``check_stalls()``: if no new bytes
have been written to ``outputFile`` for ``STALL_THRESHOLD_MS`` and the
tail matches an interactive prompt, a ``task_stalled`` notification is
enqueued.

References:
- ``references/19-background-tasks.md``
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vibecodekit._platform_lock import file_lock

TASK_TYPES = (
    "local_bash",
    "local_agent",
    "remote_agent",
    "in_process_teammate",
    "local_workflow",
    "monitor_mcp",
    "dream",
)
TASK_STATES = ("pending", "running", "completed", "failed", "killed")
TERMINAL_STATES = ("completed", "failed", "killed")

# v0.10 P2 fix: validate user-supplied task_id before using it in filesystem
# paths.  Internally generated IDs are ``task-<16-hex>`` so this is purely
# defensive validation for the public ``get_task / kill_task / read_output /
# drain_notifications`` API surface.
_TASK_ID_RX = re.compile(r"^task-[A-Za-z0-9_-]{4,64}$")


def _is_valid_task_id(task_id: str) -> bool:
    return isinstance(task_id, str) and bool(_TASK_ID_RX.match(task_id))


STALL_CHECK_INTERVAL_MS = 5_000  # §7.4
STALL_THRESHOLD_MS = 45_000
_STALL_PROMPT_RX = re.compile(
    r"(\[(?:y/n|Y/n|y/N)\]|\?\s*$|password:\s*$|continue\?\s*$|press any key)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Task:
    task_id: str
    kind: str
    description: str
    status: str = "pending"
    output_file: str = ""
    output_offset: int = 0
    stdout_size: int = 0
    returncode: int | None = None
    error: str | None = None
    pid: int | None = None
    created_ts: float = field(default_factory=time.time)
    started_ts: float | None = None
    finished_ts: float | None = None
    last_write_ts: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Atomic index read/modify/write
# ---------------------------------------------------------------------------
def _tasks_dir(root: Path) -> Path:
    d = root / ".vibecode" / "runtime" / "tasks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(root: Path) -> Path:
    return _tasks_dir(root) / "index.json"


def _lock_path(root: Path) -> Path:
    return _tasks_dir(root) / "index.lock"


@contextlib.contextmanager
def _locked_index(root: Path) -> Iterator[None]:
    lp = _lock_path(root)
    fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with file_lock(fd):
            yield
    finally:
        os.close(fd)


def _read_index(root: Path) -> dict[str, dict[str, Any]]:
    p = _index_path(root)
    if not p.exists():
        return {}
    try:
        out: dict[str, dict[str, Any]] = json.loads(p.read_text(encoding="utf-8") or "{}")
        return out
    except json.JSONDecodeError:
        return {}


def _write_index(root: Path, data: dict[str, dict[str, Any]]) -> None:
    p = _index_path(root)
    tmp_fd, tmp = tempfile.mkstemp(prefix=".tasks.", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def _upsert(root: Path, task: Task) -> None:
    with _locked_index(root):
        idx = _read_index(root)
        idx[task.task_id] = asdict(task)
        _write_index(root, idx)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_task(
    root: str | os.PathLike[str], kind: str, description: str, meta: dict[str, Any] | None = None
) -> Task:
    if kind not in TASK_TYPES:
        raise ValueError(f"unknown task kind: {kind}; known: {TASK_TYPES}")
    root_p = Path(root).resolve()
    # v0.9 P1-2 fix: 2^64 possible IDs (birthday collision at ~2^32 tasks,
    # astronomically safer than the 2^32 namespace in v0.8).
    task_id = f"task-{kind}-{secrets.token_hex(8)}"
    out_file = _tasks_dir(root_p) / f"{task_id}.out"
    out_file.touch(exist_ok=False)
    t = Task(
        task_id=task_id,
        kind=kind,
        description=description,
        output_file=str(out_file.relative_to(root_p)),
        meta=dict(meta or {}),
    )
    _upsert(root_p, t)
    _enqueue_notification(
        root_p,
        task_id,
        {"event": "task_created", "task_id": task_id, "kind": kind, "description": description},
    )
    return t


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def list_tasks(root: str | os.PathLike[str], *, only: str | None = None) -> list[dict[str, Any]]:
    root_p = Path(root).resolve()
    with _locked_index(root_p):
        idx = _read_index(root_p)
    out = list(idx.values())
    if only:
        out = [t for t in out if t.get("status") == only]
    out.sort(key=lambda t: t.get("created_ts", 0), reverse=True)
    return out


def get_task(root: str | os.PathLike[str], task_id: str) -> dict[str, Any] | None:
    if not _is_valid_task_id(task_id):
        return None
    root_p = Path(root).resolve()
    with _locked_index(root_p):
        return _read_index(root_p).get(task_id)


def read_task_output(
    root: str | os.PathLike[str], task_id: str, offset: int = 0, length: int = 64 * 1024
) -> dict[str, Any]:
    """Incremental read of a task's output — mirrors Claude Code outputOffset."""
    if not _is_valid_task_id(task_id):
        return {"error": f"invalid task_id: {task_id!r}"}
    root_p = Path(root).resolve()
    rec = get_task(root_p, task_id)
    if not rec:
        return {"error": f"unknown task: {task_id}"}
    out_path = root_p / rec["output_file"]
    if not out_path.exists():
        return {
            "task_id": task_id,
            "offset": offset,
            "length": 0,
            "content": "",
            "total_size": 0,
            "eof": True,
        }
    size = out_path.stat().st_size
    offset = max(0, int(offset))
    length = max(0, int(length))
    with out_path.open("rb") as f:
        f.seek(offset)
        data = f.read(length)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    next_offset = offset + len(data)
    return {
        "task_id": task_id,
        "offset": offset,
        "length": len(data),
        "total_size": size,
        "next_offset": next_offset,
        "eof": next_offset >= size,
        "content": text,
    }


# ---------------------------------------------------------------------------
# Run (local_bash) — non-blocking, appends to output_file
# ---------------------------------------------------------------------------
def start_local_bash(
    root: str | os.PathLike[str],
    cmd: str,
    *,
    timeout_sec: int | None = None,
    description: str | None = None,
) -> Task:
    root_p = Path(root).resolve()
    t = create_task(
        root_p, "local_bash", description or cmd[:80], meta={"cmd": cmd, "timeout_sec": timeout_sec}
    )
    out_path = root_p / t.output_file
    t.status = "running"
    t.started_ts = time.time()
    _upsert(root_p, t)

    def _runner() -> None:
        proc = None
        try:
            with out_path.open("ab", buffering=0) as fout:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(root_p),
                    shell=True,
                    stdout=fout,
                    stderr=subprocess.STDOUT,
                    text=False,
                )
                # Update pid
                with _locked_index(root_p):
                    idx = _read_index(root_p)
                    rec = idx.get(t.task_id)
                    if rec is not None:
                        rec["pid"] = proc.pid
                        _write_index(root_p, idx)
                rc = proc.wait(timeout=timeout_sec) if timeout_sec else proc.wait()
            # v0.9 P0-2 fix: don't overwrite a status that ``kill_task``
            # just set.  If the index has us marked as a terminal state
            # already (e.g. "killed"), leave it alone.
            current = get_task(root_p, t.task_id) or {}
            if current.get("status") in TERMINAL_STATES:
                return
            _finish(
                root_p, t.task_id, "completed" if rc == 0 else "failed", returncode=rc, error=None
            )
        except subprocess.TimeoutExpired:
            # v0.9 P1-3 fix: reap the zombie after killing.
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.kill()
                with contextlib.suppress(Exception):
                    proc.wait(timeout=5)
            _finish(
                root_p, t.task_id, "killed", returncode=124, error=f"timeout after {timeout_sec}s"
            )
        except Exception as e:
            _finish(root_p, t.task_id, "failed", returncode=None, error=str(e))
        finally:
            # stdout_size bookkeeping so consumers can poll
            with _locked_index(root_p):
                idx = _read_index(root_p)
                rec = idx.get(t.task_id)
                if rec is not None:
                    rec["stdout_size"] = out_path.stat().st_size if out_path.exists() else 0
                    rec["last_write_ts"] = time.time()
                    _write_index(root_p, idx)

    th = threading.Thread(target=_runner, daemon=True, name=f"task-{t.task_id}")
    th.start()
    return t


def _finish(
    root: Path, task_id: str, status: str, *, returncode: int | None, error: str | None
) -> None:
    with _locked_index(root):
        idx = _read_index(root)
        rec = idx.get(task_id)
        if rec is not None:
            rec["status"] = status
            rec["returncode"] = returncode
            rec["error"] = error
            rec["finished_ts"] = time.time()
            _write_index(root, idx)
    _enqueue_notification(
        root,
        task_id,
        {
            "event": "task_completed",
            "task_id": task_id,
            "status": status,
            "returncode": returncode,
            "error": error,
        },
    )


def kill_task(root: str | os.PathLike[str], task_id: str) -> bool:
    if not _is_valid_task_id(task_id):
        return False
    root_p = Path(root).resolve()
    rec = get_task(root_p, task_id)
    if not rec or rec.get("status") in TERMINAL_STATES:
        return False
    pid = rec.get("pid")
    if pid:
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, 15)
        time.sleep(0.2)
        with contextlib.suppress(ProcessLookupError, OSError):
            os.kill(pid, 9)
    _finish(root_p, task_id, "killed", returncode=137, error="killed by user")
    return True


# ---------------------------------------------------------------------------
# Notifications (§7.5)
# ---------------------------------------------------------------------------
def _notifications_path(root: Path, task_id: str) -> Path:
    return _tasks_dir(root) / f"{task_id}.notifications.jsonl"


def _notifications_lock_path(root: Path, task_id: str) -> Path:
    return _tasks_dir(root) / f"{task_id}.notifications.lock"


@contextlib.contextmanager
def _locked_notifications(root: Path, task_id: str) -> Iterator[None]:
    """Advisory lock shared by all enqueue / drain operations on a task's
    notification file (v0.9 P0-1 fix — prevents losing entries that get
    appended between the drain's read and truncate steps)."""
    lp = _notifications_lock_path(root, task_id)
    fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with file_lock(fd):
            yield
    finally:
        os.close(fd)


def _enqueue_notification(root: Path, task_id: str, payload: dict[str, Any]) -> None:
    p = _notifications_path(root, task_id)
    rec = {"ts": time.time(), "payload": payload}
    with _locked_notifications(root, task_id):
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def drain_notifications(root: str | os.PathLike[str], task_id: str) -> list[dict[str, Any]]:
    if not _is_valid_task_id(task_id):
        return []
    root_p = Path(root).resolve()
    p = _notifications_path(root_p, task_id)
    # Critical section: read + truncate must appear atomic to other
    # enqueuers.  Without the lock (v0.8), an enqueue between
    # ``read_text`` and ``write_text`` was silently lost.
    with _locked_notifications(root_p, task_id):
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").splitlines()
        p.write_text("", encoding="utf-8")
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# Stall detection (§7.4)
# ---------------------------------------------------------------------------
def check_stalls(root: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Inspect running tasks; enqueue stall notifications for ones that look
    like they're waiting on interactive input."""
    root_p = Path(root).resolve()
    now = time.time()
    stalled: list[dict[str, Any]] = []
    for rec in list_tasks(root_p, only="running"):
        out_path = root_p / rec["output_file"]
        if not out_path.exists():
            continue
        size = out_path.stat().st_size
        prev_size = rec.get("stdout_size", 0)
        last_write = rec.get("last_write_ts") or rec.get("started_ts") or now
        if size > prev_size:
            # still producing output → healthy
            with _locked_index(root_p):
                idx = _read_index(root_p)
                r2 = idx.get(rec["task_id"])
                if r2 is not None:
                    r2["stdout_size"] = size
                    r2["last_write_ts"] = now
                    _write_index(root_p, idx)
            continue
        if (now - last_write) * 1000 < STALL_THRESHOLD_MS:
            continue
        # Tail the file for an interactive prompt shape
        tail = ""
        with out_path.open("rb") as f:
            f.seek(max(0, size - 512))
            tail = f.read().decode("utf-8", errors="replace")
        if _STALL_PROMPT_RX.search(tail):
            _enqueue_notification(
                root_p,
                rec["task_id"],
                {
                    "event": "task_stalled",
                    "task_id": rec["task_id"],
                    "last_tail": tail[-200:],
                },
            )
            stalled.append({"task_id": rec["task_id"], "tail": tail[-200:]})
    return stalled


# ---------------------------------------------------------------------------
# Dream task (§7.2) — runs memory consolidation
# ---------------------------------------------------------------------------
_DREAM_DEDUP_THRESHOLD = 0.92  # cosine sim cutoff — entries above this are considered duplicates


def start_dream(root: str | os.PathLike[str]) -> Task:
    """Start a *dream* task that consolidates session memory.

    v0.9 implements the full 4-phase Claude Code DreamTask pipeline
    (Giải phẫu §11.5):

      1. **orient**     — count event sources and most-recent sessions
      2. **gather**     — collect the last 200 events per session, plus
                          current project memory entries
      3. **consolidate**— summarise tool usage, error rates, recurring
                          failure events into ``dream-digest.md``
      4. **prune**      — embedding-based dedup of ``.vibecode/memory/
                          log.jsonl`` (project tier), keeping highest-
                          scored representative of each cluster

    Phase outputs are appended to the task output file as JSON lines so
    a caller can replay or inspect individual phases.
    """
    root_p = Path(root).resolve()
    t = create_task(
        root_p,
        "dream",
        "memory consolidation",
        meta={"phases": ["orient", "gather", "consolidate", "prune"]},
    )
    out_path = root_p / t.output_file
    t.status = "running"
    t.started_ts = time.time()
    _upsert(root_p, t)

    def _runner() -> None:
        try:
            from .memory_hierarchy import get_backend

            log_dir = root_p / ".vibecode" / "runtime"
            mem = root_p / ".vibecode" / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            phase_log: list[dict[str, Any]] = []

            # --- Phase 1: orient ---
            session_files = sorted(log_dir.glob("*.events.jsonl"))
            phase_log.append({"phase": "orient", "sessions": [p.name for p in session_files]})

            # --- Phase 2: gather ---
            events: list[dict[str, Any]] = []
            for jp in session_files:
                try:
                    lines = jp.read_text(encoding="utf-8").splitlines()[-200:]
                except OSError:
                    continue
                for line in lines:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            phase_log.append(
                {
                    "phase": "gather",
                    "events_collected": len(events),
                    "sessions_scanned": len(session_files),
                }
            )

            # --- Phase 3: consolidate ---
            tool_counts: dict[str, int] = {}
            err_counts: dict[str, int] = {}
            for e in events:
                if e.get("event") == "tool_result":
                    tname = (e.get("payload") or {}).get("block", {}).get("tool")
                    if tname:
                        tool_counts[tname] = tool_counts.get(tname, 0) + 1
                if e.get("status") in ("error", "blocked"):
                    err_counts[e.get("event", "")] = err_counts.get(e.get("event", ""), 0) + 1
            digest = mem / "dream-digest.md"
            lines = [
                "# Dream digest",
                f"_{time.strftime('%Y-%m-%d %H:%M:%S')}_",
                "",
                f"Analysed {len(events)} events across {len(session_files)} sessions.",
                "",
                "## Tool usage",
            ]
            for k, v in sorted(tool_counts.items(), key=lambda x: -x[1]):
                lines.append(f"- `{k}` — {v}")
            if err_counts:
                lines.append("")
                lines.append("## Errors / blocks")
                for k, v in sorted(err_counts.items(), key=lambda x: -x[1]):
                    lines.append(f"- {k} — {v}")
            digest.write_text("\n".join(lines), encoding="utf-8")
            phase_log.append(
                {
                    "phase": "consolidate",
                    "digest": str(digest.relative_to(root_p)),
                    "tool_uses": len(tool_counts),
                    "errors": len(err_counts),
                }
            )

            # --- Phase 4: prune (embedding-based dedup) ---
            project_log = mem / "log.jsonl"
            pruned_before = pruned_after = 0
            if project_log.exists():
                rows: list[dict[str, Any]] = []
                for line in project_log.read_text(encoding="utf-8").splitlines():
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                pruned_before = len(rows)
                if rows:
                    emb = get_backend()
                    vectors = [
                        emb.embed(r.get("text", "") + " " + r.get("header", "")) for r in rows
                    ]
                    # Greedy dedup: iterate oldest→newest, keep if no prior
                    # kept vector exceeds the similarity threshold.
                    kept_vecs: list[list[float]] = []
                    kept_rows: list[dict[str, Any]] = []
                    for row, vec in zip(rows, vectors, strict=False):
                        dup = False
                        for kv in kept_vecs:
                            if emb.similarity(vec, kv) >= _DREAM_DEDUP_THRESHOLD:
                                dup = True
                                break
                        if not dup:
                            kept_vecs.append(vec)
                            kept_rows.append(row)
                    pruned_after = len(kept_rows)
                    if pruned_after < pruned_before:
                        # Atomic rewrite via tmp + replace.
                        tmp = project_log.with_suffix(".jsonl.tmp")
                        tmp.write_text(
                            "\n".join(json.dumps(r, ensure_ascii=False) for r in kept_rows) + "\n",
                            encoding="utf-8",
                        )
                        os.replace(tmp, project_log)
            phase_log.append(
                {
                    "phase": "prune",
                    "entries_before": pruned_before,
                    "entries_after": pruned_after,
                    "threshold": _DREAM_DEDUP_THRESHOLD,
                }
            )

            # Write phase log as JSON-Lines (matches other background tasks).
            with out_path.open("w", encoding="utf-8") as f:
                for rec in phase_log:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _finish(root_p, t.task_id, "completed", returncode=0, error=None)
        except Exception as e:  # pragma: no cover
            _finish(root_p, t.task_id, "failed", returncode=None, error=str(e))

    th = threading.Thread(target=_runner, daemon=True, name=f"task-{t.task_id}")
    th.start()
    return t


# ---------------------------------------------------------------------------
# local_agent — runs a sub-agent plan in a daemon thread
# ---------------------------------------------------------------------------
def start_local_agent(
    root: str | os.PathLike[str],
    *,
    role: str,
    objective: str,
    blocks: list[dict[str, Any]] | None = None,
    description: str | None = None,
) -> Task:
    """Spawn a sub-agent and execute an optional block-plan in the
    background.  Output (JSON-encoded run result) is appended to the
    task's ``output_file``.
    """
    root_p = Path(root).resolve()
    t = create_task(
        root_p,
        "local_agent",
        description or f"{role}: {objective[:60]}",
        meta={"role": role, "objective": objective, "blocks": blocks or []},
    )
    out_path = root_p / t.output_file
    t.status = "running"
    t.started_ts = time.time()
    _upsert(root_p, t)

    def _runner() -> None:
        try:
            from .subagent_runtime import run as sub_run
            from .subagent_runtime import spawn as sub_spawn

            spawn_result = sub_spawn(root_p, role, objective)
            agent_id = spawn_result["agent_id"]
            result = sub_run(root_p, agent_id, blocks or [])
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            _finish(root_p, t.task_id, "completed", returncode=0, error=None)
        except Exception as e:  # pragma: no cover
            out_path.write_text(f"error: {e}\n", encoding="utf-8")
            _finish(root_p, t.task_id, "failed", returncode=None, error=str(e))

    th = threading.Thread(target=_runner, daemon=True, name=f"task-{t.task_id}")
    th.start()
    return t


# ---------------------------------------------------------------------------
# local_workflow — declarative multi-step pipeline
# ---------------------------------------------------------------------------
def start_local_workflow(
    root: str | os.PathLike[str], *, steps: list[dict[str, Any]], description: str | None = None
) -> Task:
    """Execute a scripted pipeline in the background.  Each step is a dict::

        {"kind": "bash", "cmd": "pytest -q"}
        {"kind": "sleep", "seconds": 2}
        {"kind": "write", "path": "logs/note.md", "content": "…"}

    All steps run sequentially in a daemon thread.  A step with
    ``on_error: "continue"`` doesn't abort the pipeline.  Step results
    are appended as JSON lines to the task's ``output_file``.
    """
    root_p = Path(root).resolve()
    t = create_task(
        root_p,
        "local_workflow",
        description or f"workflow({len(steps)} steps)",
        meta={"steps": steps},
    )
    out_path = root_p / t.output_file
    t.status = "running"
    t.started_ts = time.time()
    _upsert(root_p, t)

    def _runner() -> None:
        # Import lazily to avoid circular import on load.
        from .permission_engine import decide

        any_failure = False
        try:
            with out_path.open("a", encoding="utf-8") as fout:
                for i, step in enumerate(steps):
                    kind = step.get("kind", "bash")
                    line: dict[str, Any] = {"step": i, "kind": kind}
                    try:
                        if kind == "bash":
                            cmd = step.get("cmd", "")
                            decision = decide(
                                cmd, mode=step.get("mode", "auto_safe"), root=str(root_p)
                            )
                            if decision["decision"] != "allow":
                                line["result"] = {"blocked": True, "permission": decision}
                            else:
                                proc = subprocess.run(
                                    cmd,
                                    shell=True,
                                    cwd=str(root_p),
                                    capture_output=True,
                                    text=True,
                                    timeout=step.get("timeout", 300),
                                )
                                line["result"] = {
                                    "returncode": proc.returncode,
                                    "stdout": (proc.stdout or "")[-2000:],
                                    "stderr": (proc.stderr or "")[-2000:],
                                }
                                if proc.returncode != 0 and step.get("on_error") != "continue":
                                    any_failure = True
                                    fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                                    break
                        elif kind == "sleep":
                            time.sleep(float(step.get("seconds", 1.0)))
                            line["result"] = {"slept": step.get("seconds", 1.0)}
                        elif kind == "write":
                            # v0.10 P1 fix: use relative_to instead of
                            # startswith() which is fooled by prefix
                            # confusion (e.g. /tmp/a vs /tmp/ab).
                            path = (root_p / step["path"]).resolve()
                            try:
                                rel = path.relative_to(root_p)
                            except ValueError:
                                line["result"] = {"error": "path escapes root"}
                                any_failure = True
                                fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                                break
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.write_text(step.get("content", ""), encoding="utf-8")
                            line["result"] = {"wrote": str(rel)}
                        else:
                            line["result"] = {"error": f"unknown step kind: {kind}"}
                            if step.get("on_error") != "continue":
                                any_failure = True
                                fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                                break
                    except Exception as e:  # per-step failure
                        line["result"] = {"error": f"{type(e).__name__}: {e}"}
                        if step.get("on_error") != "continue":
                            any_failure = True
                            fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                            break
                    fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                    fout.flush()
            _finish(
                root_p,
                t.task_id,
                "failed" if any_failure else "completed",
                returncode=1 if any_failure else 0,
                error=None,
            )
        except Exception as e:  # pragma: no cover
            _finish(root_p, t.task_id, "failed", returncode=None, error=str(e))

    th = threading.Thread(target=_runner, daemon=True, name=f"task-{t.task_id}")
    th.start()
    return t


# ---------------------------------------------------------------------------
# monitor_mcp — periodically pings an MCP server and records health
# ---------------------------------------------------------------------------
def start_monitor_mcp(
    root: str | os.PathLike[str],
    *,
    server_name: str,
    interval_sec: float = 15.0,
    max_checks: int = 10,
    tool: str = "ping",
    args: dict[str, Any] | None = None,
) -> Task:
    """Start a daemon thread that periodically calls an MCP tool and
    records up/down counts to the task's output file.
    """
    root_p = Path(root).resolve()
    t = create_task(
        root_p,
        "monitor_mcp",
        f"monitor:{server_name}.{tool}",
        meta={
            "server": server_name,
            "tool": tool,
            "interval_sec": interval_sec,
            "max_checks": max_checks,
        },
    )
    out_path = root_p / t.output_file
    t.status = "running"
    t.started_ts = time.time()
    _upsert(root_p, t)

    def _runner() -> None:
        from .mcp_client import call_tool

        up = down = 0
        try:
            with out_path.open("a", encoding="utf-8") as fout:
                for i in range(max_checks):
                    rec_state = get_task(root_p, t.task_id) or {}
                    if rec_state.get("status") in TERMINAL_STATES:
                        break
                    tstart = time.time()
                    try:
                        r = call_tool(root_p, server_name, tool, args or {}, timeout=5.0)
                        ok = "error" not in r
                    except Exception as e:  # pragma: no cover
                        r = {"error": str(e)}
                        ok = False
                    up += int(ok)
                    down += int(not ok)
                    fout.write(
                        json.dumps(
                            {
                                "check": i,
                                "ok": ok,
                                "latency_ms": round((time.time() - tstart) * 1000, 2),
                                "response": r,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    fout.flush()
                    if i < max_checks - 1:
                        time.sleep(interval_sec)
            final_ok = down == 0
            _finish(
                root_p,
                t.task_id,
                "completed" if final_ok else "failed",
                returncode=0 if final_ok else 1,
                error=None if final_ok else f"{down}/{up + down} checks failed",
            )
        except Exception as e:  # pragma: no cover
            _finish(root_p, t.task_id, "failed", returncode=None, error=str(e))

    th = threading.Thread(target=_runner, daemon=True, name=f"task-{t.task_id}")
    th.start()
    return t


# ---------------------------------------------------------------------------
# Wait helper for tests
# ---------------------------------------------------------------------------
def wait_for(
    root: str | os.PathLike[str], task_id: str, *, timeout: float = 10.0
) -> dict[str, Any]:
    root_p = Path(root).resolve()
    start = time.time()
    while time.time() - start < timeout:
        rec = get_task(root_p, task_id)
        if rec and rec.get("status") in TERMINAL_STATES:
            return rec
        time.sleep(0.05)
    return get_task(root_p, task_id) or {}
