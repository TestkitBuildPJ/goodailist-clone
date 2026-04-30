"""Sub-agent runtime with real ACL enforcement (Patterns #7 + #8).

Each spawned agent has an isolated workspace under
``.vibecode/runtime/agents/<agent_id>`` containing:

    state.json    — role, objective, permission_mode, parent, children
    context.md    — markdown context injected into its prompt
    events.jsonl  — private event log

When the parent invokes ``run(agent_id, blocks)``, the tool executor is
called with a ``profile`` dict that enforces the role's tool whitelist and
``can_mutate`` flag (Pattern #7 — Coordinator restriction).  High-risk
actions run in ``bubble`` mode: the decision escalates upwards to the parent
rather than being resolved locally.

References:
- ``references/07-coordinator-restriction.md``
"""

from __future__ import annotations

import contextlib
import json
import os
import secrets
import tempfile
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ._platform_lock import file_lock
from .event_bus import EventBus
from .tool_executor import execute_blocks

_READ_ONLY_TOOLS = [
    "list_files",
    "read_file",
    "grep",
    "glob",
    "task_status",
    "task_read",
    "task_notifications",
    "mcp_list",
    "memory_retrieve",
    "memory_stats",
    "approval_list",
]
_TASK_CONTROL_TOOLS = ["task_start", "task_kill"]
_MEMORY_WRITE_TOOLS = ["memory_add"]
_APPROVAL_RESPOND_TOOLS = ["approval_create", "approval_respond"]

PROFILES: dict[str, dict[str, Any]] = {
    "coordinator": {
        "can_mutate": False,
        # Coordinators CAN start / kill tasks, create approvals, and
        # inspect memory, but CANNOT write/append/delete files directly —
        # they delegate mutation to builders (§6.3).
        "tools": _READ_ONLY_TOOLS + _TASK_CONTROL_TOOLS + _APPROVAL_RESPOND_TOOLS,
        "permission_mode": "plan",
        "description": "Plans, routes, and orchestrates background tasks; cannot mutate files.",
    },
    "scout": {
        "can_mutate": False,
        "tools": _READ_ONLY_TOOLS + ["run_command"],
        "permission_mode": "plan",
        "description": "Read-only exploration; only verify/read-only commands.",
    },
    "builder": {
        "can_mutate": True,
        "tools": _READ_ONLY_TOOLS
        + _TASK_CONTROL_TOOLS
        + _MEMORY_WRITE_TOOLS
        + _APPROVAL_RESPOND_TOOLS
        + ["run_command", "write_file", "append_file"],
        "permission_mode": "default",
        "description": "Implements an approved TIP; high-risk bubble-escalates.",
    },
    "qa": {
        "can_mutate": False,
        "tools": _READ_ONLY_TOOLS + ["run_command"],
        "permission_mode": "plan",
        "description": "Quality gate / verification only.",
    },
    "security": {
        "can_mutate": False,
        "tools": _READ_ONLY_TOOLS + ["run_command"],
        "permission_mode": "plan",
        "description": "Security audit only.",
    },
    "reviewer": {
        "can_mutate": False,
        "tools": _READ_ONLY_TOOLS + ["run_command"],
        "permission_mode": "plan",
        "description": "Adversarial multi-perspective code review (7 specialists); read-only.",
    },
    "qa-lead": {
        "can_mutate": False,
        "tools": _READ_ONLY_TOOLS + ["run_command"],
        "permission_mode": "plan",
        "description": "Real-browser QA lead — coordinates checklist VN-12 + fix-loop proposals; read-only.",
    },
}


@dataclass
class AgentState:
    agent_id: str
    role: str
    objective: str
    parent: str | None = None
    permission_mode: str = "bubble"
    can_mutate: bool = False
    tools: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    status: str = "pending"
    created_ts: float = field(default_factory=time.time)


def _agent_dir(root: Path, agent_id: str) -> Path:
    d = root / ".vibecode" / "runtime" / "agents" / agent_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_lock_path(d: Path) -> Path:
    return d / "state.lock"


@contextlib.contextmanager
def _locked_state(d: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock on the agent's state directory.

    Used to serialise read-modify-write cycles on ``state.json`` (e.g. parent
    appending to ``children`` while another spawn() is doing the same).
    """
    lp = _state_lock_path(d)
    fd = os.open(str(lp), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with file_lock(fd):
            yield
    finally:
        os.close(fd)


def _atomic_write_state(path: Path, payload: dict[str, Any]) -> None:
    """Crash-safe state.json write — tmp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".state.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def spawn(
    root: str | os.PathLike[str], role: str, objective: str, parent: str | None = None
) -> dict[str, Any]:
    if role not in PROFILES:
        raise ValueError(f"unknown role: {role}; known: {list(PROFILES)}")
    root = Path(root).resolve()
    profile = PROFILES[role]
    agent_id = f"{role}-{secrets.token_hex(3)}"
    # Children of any agent run in bubble mode so high-risk actions bubble up.
    mode = "bubble" if parent is not None else profile.get("permission_mode", "plan")
    state = AgentState(
        agent_id=agent_id,
        role=role,
        objective=objective,
        parent=parent,
        permission_mode=mode,
        can_mutate=profile["can_mutate"],
        tools=list(profile["tools"]),
    )
    d = _agent_dir(root, agent_id)
    _atomic_write_state(d / "state.json", asdict(state))
    (d / "context.md").write_text(
        f"# Sub-agent `{agent_id}` — {role}\n\n"
        f"**Objective:** {objective}\n\n"
        f"**Profile:** can_mutate={state.can_mutate}, tools={state.tools}, mode={mode}\n",
        encoding="utf-8",
    )
    # v0.11.0 audit follow-up — parent.children list update under file lock to
    # eliminate the read-modify-write race when multiple children spawn from
    # the same parent concurrently (lost-update bug).
    if parent:
        parent_dir = _agent_dir(root, parent)
        parent_state_path = parent_dir / "state.json"
        if parent_state_path.exists():
            with _locked_state(parent_dir):
                ps = json.loads(parent_state_path.read_text(encoding="utf-8"))
                ps.setdefault("children", []).append(agent_id)
                _atomic_write_state(parent_state_path, ps)
    return asdict(state)


def _set_status(d: Path, sp: Path, status: str) -> dict[str, Any]:
    """Read-modify-write the agent's status field under the directory lock."""
    with _locked_state(d):
        state: dict[str, Any] = json.loads(sp.read_text(encoding="utf-8"))
        state["status"] = status
        _atomic_write_state(sp, state)
        return state


def run(
    root: str | os.PathLike[str], agent_id: str, blocks: list[dict[str, Any]]
) -> dict[str, Any]:
    root = Path(root).resolve()
    d = _agent_dir(root, agent_id)
    sp = d / "state.json"
    if not sp.exists():
        raise ValueError(f"agent not found: {agent_id}")
    state = json.loads(sp.read_text(encoding="utf-8"))
    profile = {"tools": state["tools"], "can_mutate": state["can_mutate"]}

    # If the agent cannot mutate, veto write-class tools up-front.
    if not state["can_mutate"]:
        bad = [b for b in blocks if b.get("tool") in ("write_file", "append_file", "delete_file")]
        if bad:
            _set_status(d, sp, "rejected")
            return {
                "agent_id": agent_id,
                "rejected": True,
                "reason": "role cannot mutate; blocks rejected",
                "bad_blocks": bad,
            }

    bus = EventBus(root, session_id=f"agent-{agent_id}")
    bus.emit(
        "subagent_start",
        "ok",
        {"agent_id": agent_id, "role": state["role"], "objective": state["objective"]},
    )
    _set_status(d, sp, "running")

    result = execute_blocks(
        root,
        blocks,
        session_id=bus.session_id,
        mode=state["permission_mode"],
        profile=profile,
    )
    _set_status(d, sp, "completed")
    bus.emit("subagent_stop", "ok", {"agent_id": agent_id, "result_count": len(result["results"])})
    return {"agent_id": agent_id, "result": result}


def bubble_to_parent(
    root: str | os.PathLike[str], agent_id: str, request: dict[str, Any]
) -> dict[str, Any]:
    """Record a high-risk permission request that must be resolved by the parent."""
    root = Path(root).resolve()
    d = _agent_dir(root, agent_id)
    inbox = d / "bubble.jsonl"
    with inbox.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "request": request}, ensure_ascii=False) + "\n")
    return {"ok": True, "inbox": str(inbox.relative_to(root))}


# ---------------------------------------------------------------------------
# v0.11.3 / Patch B — Command → agent auto-spawn registry
# ---------------------------------------------------------------------------
#
# Maps each slash command to the agent role it should spawn when the
# user invokes it.  ``commands_dir_layout`` walks ``.claude/commands/``
# and reads each command file's frontmatter; if the file declares
# ``agent: <role>`` that wins, otherwise the entry below is used as the
# canonical default.
#
# Commands not in the map run in the parent agent's context (the v0.11.2
# behaviour).  The parent driver uses :func:`spawn_for_command` so it
# never has to know the role itself.

DEFAULT_COMMAND_AGENT: dict[str, str] = {
    "vibe-blueprint": "coordinator",
    "vibe-scaffold": "builder",
    "vibe-module": "builder",
    "vibe-verify": "qa",
    "vibe-audit": "security",
    "vibe-scan": "scout",
    # v0.12.0 — VCK-* gstack-inspired specialist commands.
    "vck-review": "reviewer",
    "vck-cso": "security",
    "vck-qa": "qa-lead",
    "vck-qa-only": "qa-lead",
    "vck-investigate": "scout",
    "vck-canary": "qa",
    "vck-ship": "coordinator",
    # v0.14.0 — plan-review + polish commands (gstack Phase 3 + 4).
    "vck-office-hours": "reviewer",
    "vck-ceo-review": "reviewer",
    "vck-eng-review": "reviewer",
    "vck-design-consultation": "coordinator",
    "vck-design-review": "reviewer",
    "vck-learn": "scout",
    "vck-retro": "coordinator",
    "vck-second-opinion": "reviewer",
    # v0.15.0 — master pipeline router (PR-C / T6).
    "vck-pipeline": "coordinator",
}


def list_command_agent_bindings() -> dict[str, str]:
    """Return a copy of the canonical ``slash command → role`` map."""
    return dict(DEFAULT_COMMAND_AGENT)


def _parse_command_frontmatter(path: Path) -> dict[str, str]:
    """Extract YAML-ish frontmatter from a slash-command markdown file.

    Slash commands use a tiny subset of YAML (``key: value`` pairs only),
    so a regex-free parser is sufficient and avoids a yaml dependency.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: dict[str, str] = {}
    for line in text[3:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s:
            continue
        key, _, val = s.partition(":")
        out[key.strip()] = val.strip().strip("'\"")
    return out


def resolve_command_agent(command: str, commands_dir: Path | None = None) -> str | None:
    """Return the agent role bound to ``command`` (or ``None``).

    Resolution order:
      1. ``agent:`` declared in the slash command's frontmatter.
      2. :data:`DEFAULT_COMMAND_AGENT` lookup.
      3. ``None`` (run in parent context).
    """
    if commands_dir:
        cdir = Path(commands_dir)
        for fname in (f"{command}.md", f"/{command}.md"):
            p = cdir / fname.lstrip("/")
            if p.exists():
                fm = _parse_command_frontmatter(p)
                role = fm.get("agent")
                if role:
                    return role
                break
    return DEFAULT_COMMAND_AGENT.get(command)


def spawn_for_command(
    root: str | os.PathLike[str],
    command: str,
    objective: str,
    *,
    commands_dir: Path | None = None,
    parent: str | None = None,
) -> dict[str, Any]:
    """Spawn the agent bound to ``command`` (or raise if no binding).

    Use this from the slash-command driver instead of calling
    :func:`spawn` directly — it preserves the
    "frontmatter overrides default" precedence so end users can pin a
    different agent per command without touching code.
    """
    role = resolve_command_agent(command, commands_dir=commands_dir)
    if role is None:
        raise LookupError(
            f"no agent binding for command {command!r}; "
            f"add ``agent:`` to .claude/commands/{command}.md or set "
            f"DEFAULT_COMMAND_AGENT[{command!r}]"
        )
    return spawn(root, role, objective, parent=parent)
