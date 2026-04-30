"""Tool executor — path-safe, permission-checked, hook-gated (Pattern #5 + #10).

Implements the relevant parts of the 14-step pipeline from the book:

    1.  ACL check against sub-agent profile (tools whitelist)
    2.  Path-safety canonicalisation  (Path.resolve + is_relative_to)
    3.  pre-tool hook (receives TOOL name, INPUT JSON, and COMMAND argv)
    4.  Permission decision for ``run_command``
    5.  Tool execution proper
    6.  Tool-result budget (truncation signal — not silent)
    7.  post-tool hook (may veto / rewrite result)
    8.  Context modifier emission

For concurrent batches we use a ThreadPoolExecutor; exclusive batches run
serially.  Critical-tool abort: if a ``run_command`` in an exclusive batch
fails (returncode != 0) we short-circuit the batch but continue the run
(the query loop decides what to do about it).

References:
- ``references/04-concurrency-partitioning.md``
- ``references/05-streaming-tool-execution.md``
- ``references/15-plugin-sandbox.md``
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ._logging import get_logger
from .context_modifier_chain import apply_modifiers
from .event_bus import EventBus
from .hook_interceptor import is_blocked, run_hooks
from .permission_engine import decide
from .tool_schema_registry import partition_tool_blocks

_log = get_logger("vibecodekit.tool_executor")


MAX_READ_BYTES = 200_000  # hard cap for read_file
MAX_STDOUT_CHARS = 20_000  # cap for run_command outputs
DEFAULT_CMD_TIMEOUT = 300  # seconds
MAX_FILES_LISTED = 2000


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _resolve_under_root(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root`` rejecting escape via symlink / '..' / absolute path.

    Uses ``Path.resolve(strict=False)`` + ``is_relative_to`` (Py >=3.9).
    """
    if not rel:
        raise ValueError("empty path")
    # Absolute input must still live under the root after resolution.
    target = (root / rel).resolve() if not os.path.isabs(rel) else Path(rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as e:
        raise ValueError(f"path escapes project root: {target}") from e
    return target


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _tool_list_files(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    rel = inp.get("path", ".")
    depth = int(inp.get("depth", 1))
    target = _resolve_under_root(root, rel)
    if not target.exists():
        return {"missing": str(target)}
    out: list[str] = []
    if target.is_file():
        return {"files": [str(target.relative_to(root))]}
    prefix_len = len(str(root)) + 1
    for p in sorted(target.rglob("*")):
        parts = p.relative_to(target).parts
        if len(parts) > depth:
            continue
        out.append(str(p)[prefix_len:])
        if len(out) >= MAX_FILES_LISTED:
            return {"files": out, "truncated": True, "limit": MAX_FILES_LISTED}
    return {"files": out, "truncated": False}


def _tool_read_file(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    """Read a file slice.

    Accepts optional ``offset`` (byte position) and ``length`` (bytes to
    read).  Mirrors Claude Code's ``outputOffset`` pattern (Giải phẫu
    §7.4): allows incremental reading of long outputs without re-reading
    from the start.  Default slice is ``[0, MAX_READ_BYTES]``.
    """
    rel = inp["path"]
    optional = bool(inp.get("optional", False))
    offset = max(0, int(inp.get("offset", 0)))
    length = int(inp.get("length", MAX_READ_BYTES))
    length = max(0, min(length, MAX_READ_BYTES))
    try:
        target = _resolve_under_root(root, rel)
    except ValueError as e:
        return {"error": str(e)}
    if not target.exists():
        return {"missing": str(target)} if optional else {"error": f"not found: {target}"}
    total_size = target.stat().st_size
    with target.open("rb") as f:
        f.seek(offset)
        data = f.read(length + 1)  # +1 sentinel byte to detect truncation
    truncated = len(data) > length
    if truncated:
        data = data[:length]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    next_offset = offset + len(data)
    return {
        "path": str(target.relative_to(root)),
        "offset": offset,
        "length": len(data),
        "bytes": len(data),
        "total_size": total_size,
        "next_offset": next_offset,
        "eof": next_offset >= total_size,
        "truncated": truncated,
        "max_bytes": MAX_READ_BYTES,
        "content": text,
    }


def _tool_grep(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    pattern = inp["pattern"]
    glob = inp.get("glob", "**/*")
    case_insensitive = bool(inp.get("ignore_case", False))
    max_results = int(inp.get("max_results", 200))
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        return {"error": f"invalid regex: {e}"}
    matches: list[dict[str, Any]] = []
    search_root = _resolve_under_root(root, inp.get("path", "."))
    for p in sorted(search_root.glob(glob)):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                matches.append(
                    {"path": str(p.relative_to(root)), "lineno": lineno, "line": line[:500]}
                )
                if len(matches) >= max_results:
                    return {"matches": matches, "truncated": True}
    return {"matches": matches, "truncated": False}


def _tool_run_command(
    root: Path,
    inp: dict[str, Any],
    bus: EventBus,
    mode: str,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cmd = inp.get("cmd") or inp.get("command") or ""
    timeout = int(inp.get("timeout", DEFAULT_CMD_TIMEOUT))
    # The executor re-checks permission here; the query loop is expected to
    # have already passed ``mode`` for consistency.
    decision = decide(cmd, mode=mode, root=str(root), rules=rules)
    if decision["decision"] != "allow":
        return {"permission": decision, "executed": False}
    try:
        p = subprocess.Popen(
            cmd,
            cwd=str(root),
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # allow killing the whole process tree
        )
        try:
            stdout, stderr = p.communicate(timeout=timeout)
            returncode = p.returncode
        except subprocess.TimeoutExpired:
            # Kill the whole process group (POSIX only).  On Windows
            # fall back to ``p.terminate()``/``p.kill()``.
            if os.name == "posix":
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError, AttributeError):
                    pass
            else:  # pragma: no cover — Windows
                with contextlib.suppress(Exception):
                    p.terminate()
            try:
                stdout, stderr = p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError, AttributeError):
                        pass
                else:  # pragma: no cover — Windows
                    with contextlib.suppress(Exception):
                        p.kill()
                stdout, stderr = p.communicate()
            returncode = -1
            stderr = (stderr or "") + f"\n[vibecode] killed after {timeout}s timeout"
        return {
            "cmd": cmd,
            "returncode": returncode,
            "timeout": timeout,
            "stdout": (stdout or "")[-MAX_STDOUT_CHARS:],
            "stderr": (stderr or "")[-MAX_STDOUT_CHARS:],
            "executed": True,
            "permission": decision,
        }
    except Exception as e:
        return {"cmd": cmd, "error": str(e), "executed": False}


def _tool_write_file(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    rel = inp["path"]
    content = inp.get("content", "")
    target = _resolve_under_root(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding=inp.get("encoding", "utf-8"))
    return {
        "path": str(target.relative_to(root)),
        "bytes": len(content),
        "modifier": {"kind": "file_changed", "path": str(target.relative_to(root))},
    }


def _tool_append_file(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    rel = inp["path"]
    content = inp.get("content", "")
    target = _resolve_under_root(root, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding=inp.get("encoding", "utf-8")) as f:
        f.write(content)
    return {
        "path": str(target.relative_to(root)),
        "appended": len(content),
        "modifier": {"kind": "file_changed", "path": str(target.relative_to(root))},
    }


def _tool_delete_file(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    # Always blocked in the schema; we return a clear permission payload.
    return {
        "permission": {
            "decision": "deny",
            "class": "blocked",
            "reason": "delete_file is always blocked; use run_command with explicit approval",
        }
    }


def _tool_glob(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    pattern = inp.get("pattern") or "**/*"
    max_results = int(inp.get("max_results", 500))
    base = _resolve_under_root(root, inp.get("path", "."))
    matches: list[str] = []
    for p in sorted(base.glob(pattern)):
        if p.is_file():
            matches.append(str(p.relative_to(root)))
            if len(matches) >= max_results:
                return {"matches": matches, "truncated": True, "limit": max_results}
    return {"matches": matches, "truncated": False}


def _tool_task_start(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import task_runtime

    kind = inp.get("kind", "local_bash")
    if kind == "local_bash":
        cmd = inp.get("cmd") or inp.get("command") or ""
        if not cmd:
            return {"error": "cmd is required for local_bash"}
        decision = decide(cmd, mode=inp.get("mode", "auto_safe"), root=str(root))
        if decision["decision"] != "allow":
            return {"permission": decision, "executed": False}
        t = task_runtime.start_local_bash(
            root,
            cmd,
            timeout_sec=int(inp["timeout_sec"]) if inp.get("timeout_sec") else None,
            description=inp.get("description"),
        )
    elif kind == "dream":
        t = task_runtime.start_dream(root)
    elif kind == "local_agent":
        role = inp.get("role")
        objective = inp.get("objective")
        if not role or not objective:
            return {"error": "local_agent requires 'role' and 'objective'"}
        t = task_runtime.start_local_agent(
            root,
            role=role,
            objective=objective,
            blocks=inp.get("blocks") or [],
            description=inp.get("description"),
        )
    elif kind == "local_workflow":
        steps = inp.get("steps") or []
        if not steps:
            return {"error": "local_workflow requires non-empty 'steps'"}
        t = task_runtime.start_local_workflow(
            root,
            steps=steps,
            description=inp.get("description"),
        )
    elif kind == "monitor_mcp":
        server = inp.get("server")
        if not server:
            return {"error": "monitor_mcp requires 'server'"}
        t = task_runtime.start_monitor_mcp(
            root,
            server_name=server,
            tool=inp.get("tool", "ping"),
            args=inp.get("args") or {},
            interval_sec=float(inp.get("interval_sec", 15.0)),
            max_checks=int(inp.get("max_checks", 10)),
        )
    else:
        return {
            "error": f"unsupported task kind '{kind}' "
            f"(supported: {', '.join(task_runtime.TASK_TYPES)})"
        }
    return {"task_id": t.task_id, "kind": t.kind, "status": t.status, "output_file": t.output_file}


def _tool_task_status(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import task_runtime

    tid = inp.get("task_id")
    if tid:
        rec = task_runtime.get_task(root, tid)
        return {"task": rec} if rec else {"error": f"unknown task: {tid}"}
    return {"tasks": task_runtime.list_tasks(root, only=inp.get("only"))}


def _tool_task_read(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import task_runtime

    tid = inp.get("task_id")
    if not tid:
        return {"error": "task_id is required"}
    return task_runtime.read_task_output(
        root,
        tid,
        offset=int(inp.get("offset", 0)),
        length=int(inp.get("length", 64 * 1024)),
    )


def _tool_task_kill(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import task_runtime

    tid = inp.get("task_id")
    if not tid:
        return {"error": "task_id is required"}
    return {"killed": task_runtime.kill_task(root, tid)}


def _tool_task_notifications(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import task_runtime

    tid = inp.get("task_id")
    if not tid:
        return {"error": "task_id is required"}
    return {"notifications": task_runtime.drain_notifications(root, tid)}


def _tool_mcp_list(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import mcp_client

    return {"servers": mcp_client.list_servers(root)}


def _tool_mcp_call(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import mcp_client

    name = inp.get("server")
    tool = inp.get("tool")
    if not name or not tool:
        return {"error": "server and tool are required"}
    return mcp_client.call_tool(
        root, name, tool, args=inp.get("args") or {}, timeout=float(inp.get("timeout", 10.0))
    )


def _tool_memory_retrieve(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import memory_hierarchy

    q = inp.get("query") or ""
    if not q:
        return {"error": "query is required"}
    return {
        "results": memory_hierarchy.retrieve(
            root,
            q,
            top_k=int(inp.get("top_k", 8)),
            backend=inp.get("backend"),
            tiers=inp.get("tiers"),
            lexical_weight=float(inp.get("lexical_weight", 0.5)),
        )
    }


def _tool_memory_add(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import memory_hierarchy

    tier = inp.get("tier", "project")
    text = inp.get("text")
    if not text:
        return {"error": "text is required"}
    return memory_hierarchy.add_entry(
        root,
        tier,
        text=text,
        header=inp.get("header", "(entry)"),
        source=inp.get("source", "log.jsonl"),
    )


def _tool_memory_stats(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import memory_hierarchy

    return {"stats": memory_hierarchy.tier_stats(root)}


def _tool_approval_create(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import approval_contract

    return approval_contract.create(
        root,
        kind=inp.get("kind", "elicitation"),
        title=inp.get("title", "Approval required"),
        summary=inp.get("summary", ""),
        risk=inp.get("risk", "medium"),
        reason=inp.get("reason", ""),
        context=inp.get("context") or {},
        options=inp.get("options"),
        preview=inp.get("preview"),
        suggested=inp.get("suggested"),
        deadline_sec=inp.get("deadline_sec"),
    )


def _tool_approval_list(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import approval_contract

    return {"pending": approval_contract.list_pending(root)}


def _tool_approval_respond(root: Path, inp: dict[str, Any]) -> dict[str, Any]:
    from . import approval_contract

    aid = inp.get("approval_id")
    choice = inp.get("choice")
    if not aid or not choice:
        return {"error": "approval_id and choice are required"}
    return approval_contract.respond(root, aid, choice=choice, note=inp.get("note", ""))


TOOL_IMPL = {
    "list_files": _tool_list_files,
    "read_file": _tool_read_file,
    "grep": _tool_grep,
    "glob": _tool_glob,
    "write_file": _tool_write_file,
    "append_file": _tool_append_file,
    "delete_file": _tool_delete_file,
    "task_start": _tool_task_start,
    "task_status": _tool_task_status,
    "task_read": _tool_task_read,
    "task_kill": _tool_task_kill,
    "task_notifications": _tool_task_notifications,
    "mcp_list": _tool_mcp_list,
    "mcp_call": _tool_mcp_call,
    "memory_retrieve": _tool_memory_retrieve,
    "memory_add": _tool_memory_add,
    "memory_stats": _tool_memory_stats,
    "approval_create": _tool_approval_create,
    "approval_list": _tool_approval_list,
    "approval_respond": _tool_approval_respond,
}


# ---------------------------------------------------------------------------
# Execute one block / batch
# ---------------------------------------------------------------------------


def execute_one(
    root: Path,
    block: dict[str, Any],
    bus: EventBus,
    mode: str,
    profile: dict[str, Any] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute a single tool block end-to-end, with hook + ACL + permission."""
    tool = block.get("tool") or ""
    inp = block.get("input") or {}

    # Sub-agent ACL (Pattern #7 / §6.2.2)
    if profile is not None:
        allowed = profile.get("tools") or []
        if "*" not in allowed and tool not in allowed:
            return {
                "block": block,
                "status": "deny",
                "result": {"error": f"tool '{tool}' not in agent profile"},
                "hooks": {"pre": [], "post": []},
            }

    pre_cmd_repr = ""
    if tool == "run_command":
        pre_cmd_repr = inp.get("cmd") or inp.get("command") or ""

    pre = run_hooks(
        str(root), "pre_tool_use", {"tool": tool, "input": inp, "command": pre_cmd_repr}
    )
    if is_blocked(pre):
        return {
            "block": block,
            "status": "blocked",
            "result": {"error": "blocked by pre_tool_use hook"},
            "hooks": {"pre": pre, "post": []},
        }

    # Permission for run_command (other tools are gated by the schema)
    if tool == "run_command":
        permission = decide(pre_cmd_repr, mode=mode, root=str(root), rules=rules)
        if permission["decision"] != "allow":
            return {
                "block": block,
                "status": "deny",
                "result": {"permission": permission},
                "hooks": {"pre": pre, "post": []},
            }

    # Dispatch.  ``run_command`` is special-cased here because nó cần
    # ``bus`` / ``mode`` / ``rules`` (3 tham số ngoài shape ``(root, inp)``
    # của các tool khác trong ``TOOL_IMPL``); vì thế nó KHÔNG đăng ký
    # trong ``TOOL_IMPL`` mà được gọi trực tiếp.  Cycle 7 PR1: phải kiểm
    # tra special-case TRƯỚC khi ``impl is None`` raise unknown — bug cũ
    # khiến ``run_command`` qua ``execute_blocks`` luôn trả "unknown tool".
    if tool == "run_command":
        try:
            out = _tool_run_command(root, inp, bus, mode, rules=rules)
            status = "ok" if "error" not in out else "error"
        except Exception as e:  # pragma: no cover - defensive
            out = {"error": f"{type(e).__name__}: {e}"}
            status = "error"
    else:
        impl = TOOL_IMPL.get(tool)
        if impl is None:
            return {
                "block": block,
                "status": "error",
                "result": {"error": f"unknown tool '{tool}'"},
                "hooks": {"pre": pre, "post": []},
            }
        try:
            out = impl(root, inp)
            status = "ok" if "error" not in out else "error"
        except Exception as e:  # pragma: no cover - defensive
            out = {"error": f"{type(e).__name__}: {e}"}
            status = "error"

    post = run_hooks(
        str(root), "post_tool_use", {"tool": tool, "input": inp, "result": out, "status": status}
    )
    if is_blocked(post):
        return {
            "block": block,
            "status": "blocked_post",
            "result": out,
            "hooks": {"pre": pre, "post": post},
        }

    return {"block": block, "status": status, "result": out, "hooks": {"pre": pre, "post": post}}


def execute_blocks(
    root: str | os.PathLike[str],
    blocks: list[dict[str, Any]],
    session_id: str | None = None,
    mode: str = "default",
    profile: dict[str, Any] | None = None,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    bus = EventBus(root, session_id)
    batches = partition_tool_blocks(blocks)
    bus.emit(
        "tool_partitioned",
        "ok",
        {"batches": [{"safe": b["safe"], "count": len(b["blocks"])} for b in batches]},
    )
    _log.info(
        "tool_plan_start",
        extra={
            "session_id": bus.session_id,
            "batch_count": len(batches),
            "block_count": len(blocks),
            "mode": mode,
        },
    )

    results: list[dict[str, Any]] = []
    modifiers: list[dict[str, Any]] = []
    for batch in batches:
        if batch["safe"]:
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = [
                    ex.submit(execute_one, root, b, bus, mode, profile, rules)
                    for b in batch["blocks"]
                ]
                for fut in as_completed(futs):
                    r = fut.result()
                    results.append(r)
                    bus.emit(
                        "tool_result",
                        r.get("status", "ok"),
                        {"block": r["block"], "status": r["status"]},
                    )
        else:
            # Exclusive: run serially; if a critical run_command fails with non-zero, abort the rest of the batch.
            for b in batch["blocks"]:
                r = execute_one(root, b, bus, mode, profile, rules)
                results.append(r)
                bus.emit(
                    "tool_result",
                    r.get("status", "ok"),
                    {"block": r["block"], "status": r["status"]},
                )
                m = (r.get("result") or {}).get("modifier")
                if m:
                    modifiers.append(m)
                if (
                    b.get("tool") == "run_command"
                    and r["status"] != "ok"
                    and (r.get("result") or {}).get("returncode", 0) not in (0, None)
                ):
                    # Abort the rest of this batch — but not the whole execution.
                    bus.emit("batch_abort", "error", {"failed_block": b})
                    break

    context, applied = apply_modifiers(str(root), {}, modifiers)
    bus.emit(
        "context_modifiers_applied",
        "ok",
        {"applied": applied, "context_keys": list(context.keys())},
    )
    _log.info(
        "tool_plan_end",
        extra={
            "session_id": bus.session_id,
            "result_count": len(results),
            "modifiers_applied": applied,
        },
    )
    return {
        "session_id": bus.session_id,
        "event_log": str(bus.path),
        "results": results,
        "context": context,
    }


# ---------------------------------------------------------------------------
# CLI (invoked by /vibe-tools)
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Execute a tool plan JSON file.")
    ap.add_argument("plan")
    ap.add_argument("--root", default=".")
    ap.add_argument("--mode", default="default")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    blocks = plan.get("steps") or plan.get("blocks") or plan.get("tool_calls") or []
    out = execute_blocks(args.root, blocks, mode=args.mode)
    print(
        json.dumps(
            {
                "session_id": out["session_id"],
                "event_log": out["event_log"],
                "result_count": len(out["results"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    _main()
