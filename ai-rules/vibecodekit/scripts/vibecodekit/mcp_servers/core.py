"""Production MCP server exposing vibecodekit core functions.

Tools:

* ``permission_classify`` — classify a shell command (6-layer pipeline)
* ``permission_decide``   — full decision with mode + rules
* ``doctor_check``        — health-check a project layout
* ``audit_run``           — run conformance audit with threshold
* ``scaffold_list``       — list available scaffold presets
* ``scaffold_preview``    — preview a scaffold (file tree + LOC)
* ``intent_classify``     — classify free-form prose to slash commands
* ``memory_retrieve``     — 3-tier memory retrieval
* ``memory_add``          — add entry to a memory tier
* ``memory_stats``        — per-tier file/entry/byte counts
* ``dashboard_summarise`` — runtime event summary
* ``compact_run``         — 5-layer context compaction

When imported, the tool callables are available via the ``inproc``
transport.  When invoked as a module
(``python -m vibecodekit.mcp_servers.core``) it speaks full MCP stdio
JSON-RPC: ``initialize`` -> ``tools/list`` / ``tools/call`` -> clean
shutdown on EOF.

Usage with Claude Desktop / Cursor::

    {
      "mcpServers": {
        "vibecodekit": {
          "command": "python",
          "args": ["-m", "vibecodekit.mcp_servers.core"],
          "env": {"PYTHONPATH": "./scripts"}
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
import tempfile
from typing import Any

# ---------------------------------------------------------------------------
# Lazy imports — keeps startup fast; import on first call.
# ---------------------------------------------------------------------------


def _get_root(args: dict[str, Any]) -> str:
    return args.get("root", ".")


# ---------------------------------------------------------------------------
# Tool implementations (in-proc callables)
# ---------------------------------------------------------------------------


def permission_classify(command: str, mode: str = "default") -> dict:
    """Classify a shell command through the 6-layer permission pipeline."""
    from ..permission_engine import classify_cmd, decide

    cls, reason = classify_cmd(command)
    with tempfile.TemporaryDirectory() as tmp:
        d = decide(command, mode=mode, root=tmp)
    return {"class": cls, "reason": reason, "decision": d["decision"], "mode": d["mode"]}


def permission_decide(command: str, mode: str = "default", root: str = ".") -> dict:
    """Full permission decision with mode, rules, and denial store."""
    from ..permission_engine import decide

    return decide(command, mode=mode, root=root)


def doctor_check(root: str = ".", installed_only: bool = False) -> dict:
    """Health-check a vibecode project layout."""
    from ..doctor import check

    return check(root, installed_only=installed_only)


def audit_run(threshold: float = 0.85) -> dict:
    """Run the conformance audit with a given threshold."""
    from ..conformance_audit import audit

    return audit(threshold)


def scaffold_list() -> dict:
    """List available scaffold presets."""
    from ..scaffold_engine import ScaffoldEngine

    engine = ScaffoldEngine()
    presets = engine.list_presets()
    return {
        "presets": [
            {"name": p.name, "description": p.description, "stacks": list(p.stacks)}
            for p in presets
        ]
    }


def scaffold_preview(preset: str, stack: str) -> dict:
    """Preview a scaffold (file tree + estimated LOC)."""
    from ..scaffold_engine import ScaffoldEngine

    engine = ScaffoldEngine()
    plan = engine.preview(preset, stack=stack)
    return {
        "preset": plan.preset,
        "stack": plan.stack,
        "files": [{"path": sf.rel_path, "bytes": sf.bytes} for sf in plan.files],
        "estimated_loc": plan.estimated_loc,
        "post_install": list(plan.post_install),
    }


def intent_classify(prose: str) -> dict:
    """Classify free-form prose to slash commands."""
    from ..intent_router import IntentRouter

    router = IntentRouter()
    match = router.classify(prose)
    cmds = router.route(match)
    return {
        "intents": match.intents,
        "confidence": match.confidence,
        "commands": cmds,
    }


def memory_retrieve(query: str, root: str = ".", scope: str = "project", top_k: int = 5) -> dict:
    """3-tier memory retrieval."""
    from ..memory_hierarchy import retrieve

    tiers = [scope] if scope != "all" else None
    results = retrieve(root, query, top_k=top_k, tiers=tiers)
    return {"results": results}


def memory_add(
    content: str, root: str = ".", scope: str = "project", header: str = "(mcp-entry)"
) -> dict:
    """Add an entry to a memory tier."""
    from ..memory_hierarchy import add_entry

    result = add_entry(root, scope, text=content, header=header)
    return result


def memory_stats(root: str = ".") -> dict:
    """Per-tier file/entry/byte counts."""
    from ..memory_hierarchy import tier_stats

    return tier_stats(root)


def dashboard_summarise(root: str = ".") -> dict:
    """Runtime event summary."""
    from ..dashboard import summarise

    return summarise(root)


def compact_run(root: str = ".", reactive: bool = False) -> dict:
    """5-layer context compaction."""
    from ..compaction import compact

    return compact(root, reactive=reactive)


# ---------------------------------------------------------------------------
# Tool registry (MCP schema)
# ---------------------------------------------------------------------------

_TOOLS = {
    "permission_classify": {
        "fn": permission_classify,
        "description": "Classify a shell command through the 6-layer permission pipeline",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to classify"},
                "mode": {
                    "type": "string",
                    "enum": ["plan", "default", "accept_edits", "bypass", "auto", "bubble"],
                    "default": "default",
                },
            },
            "required": ["command"],
        },
    },
    "permission_decide": {
        "fn": permission_decide,
        "description": "Full permission decision with mode, rules, and denial store",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to classify"},
                "mode": {
                    "type": "string",
                    "enum": ["plan", "default", "accept_edits", "bypass", "auto", "bubble"],
                    "default": "default",
                },
                "root": {"type": "string", "default": "."},
            },
            "required": ["command"],
        },
    },
    "doctor_check": {
        "fn": doctor_check,
        "description": "Health-check a vibecode project layout",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "default": "."},
                "installed_only": {"type": "boolean", "default": False},
            },
        },
    },
    "audit_run": {
        "fn": audit_run,
        "description": "Run the conformance audit (87 internal regression probes)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.85, "minimum": 0, "maximum": 1},
            },
        },
    },
    "scaffold_list": {
        "fn": scaffold_list,
        "description": "List available scaffold presets (10 presets x 3 stacks)",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "scaffold_preview": {
        "fn": scaffold_preview,
        "description": "Preview a scaffold (file tree + estimated LOC) without writing files",
        "inputSchema": {
            "type": "object",
            "properties": {
                "preset": {
                    "type": "string",
                    "description": "Scaffold preset name (e.g. api-todo, saas, portfolio)",
                },
                "stack": {"type": "string", "description": "Stack variant (fastapi, nextjs, expo)"},
            },
            "required": ["preset", "stack"],
        },
    },
    "intent_classify": {
        "fn": intent_classify,
        "description": "Classify free-form prose to slash commands via the intent router",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prose": {"type": "string", "description": "Free-form natural language request"},
            },
            "required": ["prose"],
        },
    },
    "memory_retrieve": {
        "fn": memory_retrieve,
        "description": "Retrieve entries from the 3-tier memory hierarchy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "root": {"type": "string", "default": "."},
                "scope": {
                    "type": "string",
                    "enum": ["user", "project", "team"],
                    "default": "project",
                },
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    "memory_add": {
        "fn": memory_add,
        "description": "Add an entry to a memory tier",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "root": {"type": "string", "default": "."},
                "scope": {
                    "type": "string",
                    "enum": ["user", "project", "team"],
                    "default": "project",
                },
                "header": {
                    "type": "string",
                    "description": "Entry header/label",
                    "default": "(mcp-entry)",
                },
            },
            "required": ["content"],
        },
    },
    "memory_stats": {
        "fn": memory_stats,
        "description": "Per-tier file/entry/byte statistics for the memory hierarchy",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "default": "."},
            },
        },
    },
    "dashboard_summarise": {
        "fn": dashboard_summarise,
        "description": "Summarise runtime events (tasks, hooks, errors, MCP calls)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "default": "."},
            },
        },
    },
    "compact_run": {
        "fn": compact_run,
        "description": "Run 5-layer context compaction to reduce token usage",
        "inputSchema": {
            "type": "object",
            "properties": {
                "root": {"type": "string", "default": "."},
                "reactive": {"type": "boolean", "default": False},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# MCP stdio protocol handler (same pattern as selfcheck.py)
# ---------------------------------------------------------------------------


def _respond(rid: Any, result: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}) + "\n")
    sys.stdout.flush()


def _error(rid: Any, code: int, message: str) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": rid,
                "error": {"code": code, "message": message},
            }
        )
        + "\n"
    )
    sys.stdout.flush()


def _handle(req: dict[str, Any]) -> None:
    method = req.get("method", "")
    rid = req.get("id")
    params = req.get("params") or {}
    if method == "initialize":
        try:
            from .. import VERSION as _BUNDLE_VERSION
        except Exception:
            _BUNDLE_VERSION = "0.0.0+unknown"
        _respond(
            rid,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "vibecodekit-core", "version": _BUNDLE_VERSION},
            },
        )
    elif method == "notifications/initialized":
        return
    elif method == "tools/list":
        _respond(
            rid,
            {
                "tools": [
                    {
                        "name": name,
                        "description": meta["description"],
                        "inputSchema": meta["inputSchema"],
                    }
                    for name, meta in _TOOLS.items()
                ]
            },
        )
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        meta = _TOOLS.get(name)
        if meta is None:
            _error(rid, -32601, f"unknown tool: {name}")
            return
        try:
            result = meta["fn"](**args)
        except TypeError as e:
            _error(rid, -32602, f"bad arguments: {e}")
            return
        except Exception as e:
            _error(rid, -32000, f"{type(e).__name__}: {e}")
            return
        _respond(rid, result)
    elif method == "shutdown":
        _respond(rid, {})
    elif rid is not None:
        _error(rid, -32601, f"method not found: {method}")


def _main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _error(None, -32700, f"parse error: {e}")
            continue
        _handle(req)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
