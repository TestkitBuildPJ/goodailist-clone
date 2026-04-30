"""A tiny reference MCP server used by ``monitor_mcp`` tasks and tests.

It exposes three tools:

* ``ping()``        — always responds ``{"pong": True}``
* ``echo(msg="")``  — echoes its argument
* ``now()``         — returns the current epoch timestamp

When imported, the three callables above are available via the
``inproc`` transport.  When invoked as a module
(``python -m vibecodekit.mcp_servers.selfcheck``) it speaks full MCP
stdio JSON-RPC: ``initialize`` → ``tools/list`` / ``tools/call`` →
clean shutdown on EOF.  This is the default target for
``vibe task monitor --server selfcheck``.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any


def ping() -> dict:
    return {"pong": True, "ts": time.time()}


def echo(msg: str = "") -> dict:
    return {"echo": msg}


def now() -> dict:
    return {"ts": time.time()}


_TOOLS = {
    "ping": {
        "fn": ping,
        "description": "Always responds {pong: true}",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "echo": {
        "fn": echo,
        "description": "Echoes its argument",
        "inputSchema": {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    "now": {
        "fn": now,
        "description": "Current epoch timestamp",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


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
        # Resolve the bundle version lazily so the handshake always
        # advertises the same value as the canonical ``VERSION`` file
        # (avoids drift after a release bump).
        try:
            from .. import VERSION as _BUNDLE_VERSION
        except Exception:
            _BUNDLE_VERSION = "0.0.0+unknown"
        _respond(
            rid,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "vibecodekit-selfcheck", "version": _BUNDLE_VERSION},
            },
        )
    elif method == "notifications/initialized":
        return  # no reply for notifications
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
