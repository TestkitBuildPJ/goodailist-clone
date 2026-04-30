"""Tool schema registry + concurrency partitioning (Pattern #4).

Mirrors Claude Code's ``partitionToolCalls()`` from Giải phẫu §4.2.

Every tool declares a ``Concurrency`` mode::

    safe         always concurrency-safe
    conditional  safe iff its input says so (see is_concurrency_safe())
    exclusive    always serial
    blocked      refuse to dispatch

The partitioner greedily groups consecutive safe tools into a single batch,
preserving order for exclusive tools.  The algorithm is explicitly
"safe-by-default": any unknown tool, malformed input, or conditional tool
whose predicate throws is treated as *exclusive*.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

Concurrency = str  # "safe" | "conditional" | "exclusive" | "blocked"


@dataclass
class ToolSchema:
    name: str
    concurrency: Concurrency = "exclusive"
    predicate: Callable[[dict], bool] | None = None  # for conditional tools
    description: str = ""


# Used by tool_executor.  Conditional predicates check the *invocation input*,
# not the tool type — this is the Claude Code "per-invocation" trick (§4.2.2).
def _bash_is_read_only(inp: dict) -> bool:
    from .permission_engine import classify_cmd

    cmd = inp.get("cmd") or inp.get("command") or ""
    cls, _ = classify_cmd(cmd)
    return cls in ("read_only", "verify")


TOOLS: dict[str, ToolSchema] = {
    "list_files": ToolSchema("list_files", "safe", description="List files under a path"),
    "read_file": ToolSchema("read_file", "safe", description="Read file contents (truncated)"),
    "grep": ToolSchema("grep", "safe", description="Recursive regex search"),
    "glob": ToolSchema("glob", "safe", description="Glob pattern file search"),
    "run_command": ToolSchema(
        "run_command",
        "conditional",
        predicate=_bash_is_read_only,
        description="Shell execution; safe iff read-only",
    ),
    "write_file": ToolSchema("write_file", "exclusive", description="Write or overwrite a file"),
    "append_file": ToolSchema("append_file", "exclusive", description="Append to a file"),
    "delete_file": ToolSchema(
        "delete_file", "blocked", description="Deletion always requires approval"
    ),
    # Background tasks (Giải phẫu Ch 7) — all safe-to-batch in pure-query contexts
    # because they enqueue/read disk state without mutating semantic state.
    "task_start": ToolSchema(
        "task_start", "exclusive", description="Start a background task (local_bash|dream)"
    ),
    "task_status": ToolSchema("task_status", "safe", description="Query task index"),
    "task_read": ToolSchema(
        "task_read", "safe", description="Incremental read of a task outputFile"
    ),
    "task_kill": ToolSchema("task_kill", "exclusive", description="Kill a running task"),
    "task_notifications": ToolSchema(
        "task_notifications", "safe", description="Drain task-completion notifications"
    ),
    # MCP (Giải phẫu §2.8)
    "mcp_list": ToolSchema("mcp_list", "safe", description="List registered MCP servers"),
    "mcp_call": ToolSchema("mcp_call", "exclusive", description="Call a tool on an MCP server"),
    # Memory hierarchy (Giải phẫu Ch 11) — retrieve is safe, add is exclusive.
    "memory_retrieve": ToolSchema(
        "memory_retrieve", "safe", description="3-tier memory retrieval (user/team/project)"
    ),
    "memory_add": ToolSchema(
        "memory_add", "exclusive", description="Append an entry to a memory tier"
    ),
    "memory_stats": ToolSchema(
        "memory_stats", "safe", description="Report per-tier file/entry/byte counts"
    ),
    # Approval contract (Giải phẫu §10.4)
    "approval_create": ToolSchema(
        "approval_create", "exclusive", description="Create a structured approval request"
    ),
    "approval_list": ToolSchema(
        "approval_list", "safe", description="List pending approval requests"
    ),
    "approval_respond": ToolSchema(
        "approval_respond", "exclusive", description="Post a response to an approval request"
    ),
}


def is_concurrency_safe(block: dict) -> bool:
    name = block.get("tool") or block.get("name") or ""
    schema = TOOLS.get(name)
    if schema is None:
        return False  # unknown ⇒ exclusive
    if schema.concurrency == "safe":
        return True
    if schema.concurrency == "exclusive" or schema.concurrency == "blocked":
        return False
    if schema.concurrency == "conditional" and schema.predicate is not None:
        try:
            return bool(schema.predicate(block.get("input") or {}))
        except Exception:
            return False
    return False


def partition_tool_blocks(blocks: list[dict]) -> list[dict]:
    """Greedy concurrency partition (see §4.2)."""
    batches: list[dict] = []
    for b in blocks:
        safe = is_concurrency_safe(b)
        if safe and batches and batches[-1]["safe"]:
            batches[-1]["blocks"].append(b)
        else:
            batches.append({"safe": safe, "blocks": [b]})
    return batches
