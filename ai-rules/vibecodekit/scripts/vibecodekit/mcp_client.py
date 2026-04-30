"""MCP (Model Context Protocol) client adapter — Giải phẫu §2.8 / Ch 10.

MCP is the interop protocol Claude Code uses to connect third-party servers
(databases, filesystems, APIs) as *additional tool providers*.  Full MCP
requires JSON-RPC over stdio or HTTP+SSE — we ship:

1. Registry + two transports (``stdio``, ``inproc``).
2. A persistent ``StdioSession`` that performs the proper MCP handshake:
   ``initialize`` → (await result) → ``notifications/initialized`` →
   ``tools/list`` / ``tools/call`` → clean shutdown.
3. A fallback one-shot ``_call_stdio`` for legacy/test servers that only
   implement ``tools/call`` (used when ``handshake: false`` in the
   manifest entry — the default stays ``false`` for backwards compat).
4. A pure-Python in-process transport so unit tests don't depend on
   external binaries.

The goal is to make MCP a **first-class extension point** rather than a
hard dependency.

References:
- ``references/27-mcp-adapter.md``
"""

from __future__ import annotations

import importlib
import json
import os
import selectors
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

MANIFEST_REL = ".vibecode/runtime/mcp-servers.json"
MCP_PROTOCOL_VERSION = "2024-11-05"


def _manifest_path(root: Path) -> Path:
    return root / MANIFEST_REL


def load_manifest(root: str | os.PathLike) -> dict[str, Any]:
    root_p = Path(root).resolve()
    p = _manifest_path(root_p)
    if not p.exists():
        return {"servers": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"servers": []}


def save_manifest(root: str | os.PathLike, manifest: dict[str, Any]) -> None:
    root_p = Path(root).resolve()
    p = _manifest_path(root_p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def register_server(
    root: str | os.PathLike,
    name: str,
    *,
    transport: str = "inproc",
    command: list[str] | None = None,
    module: str | None = None,
    env: dict[str, str] | None = None,
    description: str = "",
    handshake: bool = False,
) -> dict[str, Any]:
    """Add / replace a server in the manifest.

    ``handshake=True`` makes subsequent ``call_tool`` / ``list_tools``
    wrap the call in a persistent ``StdioSession`` that performs the
    proper ``initialize`` → ``notifications/initialized`` → *request* →
    clean-shutdown sequence.  When ``handshake=False`` (the legacy
    default) we use the one-shot JSON-per-line fallback.
    """
    if transport not in ("stdio", "inproc"):
        raise ValueError(f"unsupported transport: {transport}")
    manifest = load_manifest(root)
    manifest.setdefault("servers", [])
    manifest["servers"] = [s for s in manifest["servers"] if s.get("name") != name]
    server = {
        "name": name,
        "transport": transport,
        "description": description,
        "enabled": True,
        "registered_ts": time.time(),
        "handshake": bool(handshake),
    }
    if command:
        server["command"] = list(command)
    if module:
        server["module"] = module
    if env:
        server["env"] = dict(env)
    manifest["servers"].append(server)
    save_manifest(root, manifest)
    return server


def list_servers(root: str | os.PathLike) -> list[dict[str, Any]]:
    return load_manifest(root).get("servers", [])


def disable_server(root: str | os.PathLike, name: str) -> bool:
    manifest = load_manifest(root)
    changed = False
    for s in manifest.get("servers", []):
        if s.get("name") == name and s.get("enabled", True):
            s["enabled"] = False
            changed = True
    if changed:
        save_manifest(root, manifest)
    return changed


# ---------------------------------------------------------------------------
# in-proc transport
# ---------------------------------------------------------------------------


def _call_inproc(server: dict[str, Any], tool: str, args: dict[str, Any]) -> dict[str, Any]:
    mod_name = server.get("module")
    if not mod_name:
        return {"error": "inproc transport requires 'module'"}
    try:
        mod = importlib.import_module(mod_name)
    except ImportError as e:
        return {"error": f"cannot import {mod_name}: {e}"}
    fn = getattr(mod, tool, None)
    if not callable(fn):
        return {"error": f"{mod_name}.{tool} is not callable"}
    try:
        return {"ok": True, "result": fn(**args)}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# stdio: persistent session with full handshake
# ---------------------------------------------------------------------------


class StdioSessionError(RuntimeError):
    """Raised for handshake / transport errors.  Callers should prefer
    the dict-based error envelope returned by ``call_tool()``."""


class StdioSession:
    """A persistent JSON-RPC-over-stdio session for an MCP server.

    Use as a context manager::

        with StdioSession(command=[...], env={...}) as sess:
            sess.initialize()
            tools = sess.list_tools()
            result = sess.call_tool("ping", {})
    """

    # Maximum stderr bytes retained for post-mortem (bounded ring buffer).
    STDERR_TAIL_BYTES = 64 * 1024

    def __init__(
        self, command: list[str], env: dict[str, str] | None = None, timeout: float = 10.0
    ) -> None:
        self._command = command
        self._env = env or {}
        self._timeout = max(0.1, min(600.0, float(timeout)))
        self._proc: subprocess.Popen | None = None
        self._next_id = 1
        self._lock = threading.Lock()
        self._stdout_buf = ""  # line-assembly buffer for partial reads
        self._stderr_buf = deque(maxlen=self.STDERR_TAIL_BYTES)
        self._stderr_thread: threading.Thread | None = None
        self._stderr_stop = threading.Event()
        self.server_info: dict[str, Any] = {}
        self.server_capabilities: dict[str, Any] = {}

    # Context manager -----------------------------------------------------
    def __enter__(self) -> StdioSession:
        self.open()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # Lifecycle -----------------------------------------------------------
    def open(self) -> None:
        if self._proc is not None:
            return
        env = os.environ.copy()
        env.update(self._env)
        # Binary pipes so select.select() / selectors work uniformly across
        # platforms.  We handle decoding ourselves to avoid
        # TextIOWrapper buffering from hiding bytes from select().
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=env,
        )
        # Spawn a drainer thread so stderr never fills up and deadlocks
        # the child on its next write(stderr).  We keep the last
        # ``STDERR_TAIL_BYTES`` for post-mortem inspection.
        self._stderr_stop.clear()
        self._stderr_thread = threading.Thread(
            target=self._drain_stderr,
            name="mcp-stderr-drain",
            daemon=True,
        )
        self._stderr_thread.start()

    def _drain_stderr(self) -> None:
        p = self._proc
        if p is None or p.stderr is None:
            return
        try:
            while not self._stderr_stop.is_set():
                chunk = p.stderr.read(4096)
                if not chunk:
                    break
                # deque with maxlen auto-truncates; feed bytes one by one.
                self._stderr_buf.extend(chunk)
        except (OSError, ValueError):
            pass

    def stderr_tail(self) -> bytes:
        return bytes(self._stderr_buf)

    def close(self) -> None:
        p = self._proc
        if p is None:
            return
        try:
            if p.poll() is None and p.stdin and not p.stdin.closed:
                try:
                    p.stdin.close()
                except Exception:
                    pass
            try:
                p.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                p.kill()
                try:
                    p.wait(timeout=1.0)
                except Exception:
                    pass
        finally:
            self._stderr_stop.set()
            t = self._stderr_thread
            if t is not None and t.is_alive():
                t.join(timeout=1.0)
            self._stderr_thread = None
            # Close the pipes explicitly so fds don't leak on repeated opens.
            for stream in (p.stdout, p.stderr, p.stdin):
                try:
                    if stream is not None and not stream.closed:
                        stream.close()
                except Exception:
                    pass
            self._proc = None

    # Low-level transport -------------------------------------------------
    def _send(self, obj: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise StdioSessionError("session is not open")
        data = (json.dumps(obj) + "\n").encode("utf-8")
        try:
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise StdioSessionError(f"send failed: {e}") from e

    def _recv(self) -> dict[str, Any]:
        """Read one JSON line from stdout, enforcing the session timeout.

        Uses ``selectors.DefaultSelector`` so the deadline is honoured
        even when the server hangs without writing.  Non-JSON lines
        (log noise) are skipped.  Bytes are assembled into a line buffer
        until a newline is seen.
        """
        if self._proc is None or self._proc.stdout is None:
            raise StdioSessionError("session is not open")
        deadline = time.time() + self._timeout
        sel = selectors.DefaultSelector()
        sel.register(self._proc.stdout, selectors.EVENT_READ)
        try:
            while True:
                # Drain any complete line already buffered.
                nl = self._stdout_buf.find("\n")
                while nl != -1:
                    line = self._stdout_buf[:nl].strip()
                    self._stdout_buf = self._stdout_buf[nl + 1 :]
                    if line:
                        try:
                            return json.loads(line)
                        except json.JSONDecodeError:
                            pass  # log noise, keep scanning
                    nl = self._stdout_buf.find("\n")

                remaining = deadline - time.time()
                if remaining <= 0:
                    raise StdioSessionError(f"timeout after {self._timeout}s waiting for response")
                if self._proc.poll() is not None:
                    # Drain any last bytes the OS still has for us.
                    try:
                        tail = self._proc.stdout.read() or b""
                        if tail:
                            self._stdout_buf += tail.decode("utf-8", "replace")
                            continue
                    except Exception:
                        pass
                    raise StdioSessionError(f"server exited (code={self._proc.returncode})")
                events = sel.select(timeout=min(remaining, 0.25))
                if not events:
                    continue
                try:
                    chunk = self._proc.stdout.read1(4096)
                except (OSError, ValueError) as e:
                    raise StdioSessionError(f"read failed: {e}") from e
                if not chunk:
                    # EOF on stdout; loop lets poll() detect the exit.
                    continue
                self._stdout_buf += chunk.decode("utf-8", "replace")
        finally:
            try:
                sel.unregister(self._proc.stdout)
            except (KeyError, ValueError):
                pass
            sel.close()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
            # Read until we see a response with matching id.
            for _ in range(64):
                resp = self._recv()
                if resp.get("id") == rid:
                    return resp
            raise StdioSessionError(f"no response for id={rid} within 64 frames")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        # Notifications have no id; expect no reply.
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    # Public request API (added in v0.10.3.1) ---------------------------------
    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send an arbitrary JSON-RPC request and wait for the matching response.

        Public wrapper around ``_request`` for callers that need to invoke
        MCP methods not yet covered by a typed helper (e.g. ``logging/setLevel``,
        ``resources/list``, vendor-specific extensions).  Returns the full
        response envelope (``{"jsonrpc", "id", "result" | "error"}``) unchanged
        so the caller can branch on ``error`` themselves.
        """
        return self._request(method, params or {})

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        """Send a JSON-RPC notification (no response expected).

        Public wrapper around ``_notify``.
        """
        self._notify(method, params)

    # MCP methods ---------------------------------------------------------
    def initialize(
        self, client_name: str = "vibecodekit", client_version: str | None = None
    ) -> dict[str, Any]:
        if client_version is None:
            # Defer the import to avoid bootstrap order issues; by the time
            # any caller invokes ``initialize`` the parent package is fully
            # loaded and ``VERSION`` reflects the bundle's ``VERSION`` file.
            from . import VERSION as _BUNDLE_VERSION

            client_version = _BUNDLE_VERSION
        resp = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": client_name, "version": client_version},
            },
        )
        if "error" in resp:
            raise StdioSessionError(f"initialize error: {resp['error']}")
        result = resp.get("result", {})
        self.server_info = result.get("serverInfo", {})
        self.server_capabilities = result.get("capabilities", {})
        self._notify("notifications/initialized", {})
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        resp = self._request("tools/list", {})
        if "error" in resp:
            raise StdioSessionError(f"tools/list error: {resp['error']}")
        return resp.get("result", {}).get("tools", []) or []

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )


# ---------------------------------------------------------------------------
# One-shot legacy stdio path (kept for servers without full handshake)
# ---------------------------------------------------------------------------


def _call_stdio_oneshot(
    server: dict[str, Any], tool: str, args: dict[str, Any], timeout: float = 10.0
) -> dict[str, Any]:
    cmd = server.get("command")
    if not cmd:
        return {"error": "stdio transport requires 'command'"}
    env = os.environ.copy()
    env.update(server.get("env") or {})
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        return {"error": f"cannot start MCP server: {e}"}
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool, "arguments": args},
    }
    try:
        out, err = proc.communicate(json.dumps(req) + "\n", timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"error": f"MCP server timeout after {timeout}s"}
    if proc.returncode != 0:
        return {"error": f"MCP server exit {proc.returncode}: {err.strip()}"}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return {"error": f"no JSON from MCP server; raw: {out[:200]!r}"}


def _call_stdio_handshake(
    server: dict[str, Any], tool: str, args: dict[str, Any], timeout: float = 10.0
) -> dict[str, Any]:
    cmd = server.get("command")
    if not cmd:
        return {"error": "stdio transport requires 'command'"}
    try:
        with StdioSession(cmd, env=server.get("env"), timeout=timeout) as sess:
            sess.initialize()
            return sess.call_tool(tool, args)
    except FileNotFoundError as e:
        return {"error": f"cannot start MCP server: {e}"}
    except StdioSessionError as e:
        return {"error": str(e)}


def _call_stdio(
    server: dict[str, Any], tool: str, args: dict[str, Any], timeout: float = 10.0
) -> dict[str, Any]:
    """Dispatch to handshake or one-shot based on server config."""
    if server.get("handshake"):
        return _call_stdio_handshake(server, tool, args, timeout)
    return _call_stdio_oneshot(server, tool, args, timeout)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

MIN_TIMEOUT = 0.1
MAX_TIMEOUT = 600.0


def _resolve(root: str | os.PathLike, server_name: str) -> dict[str, Any] | None:
    servers = load_manifest(root).get("servers", [])
    return next(
        (s for s in servers if s.get("name") == server_name and s.get("enabled", True)),
        None,
    )


def list_tools(root: str | os.PathLike, server_name: str, timeout: float = 10.0) -> dict[str, Any]:
    """Return the server's advertised tool catalogue.

    For ``handshake`` + ``stdio`` servers this performs a real
    ``initialize`` + ``tools/list`` roundtrip.  For ``inproc`` servers
    we enumerate public callables of the module.  Legacy one-shot stdio
    servers do not support discovery and return an error envelope.
    """
    server = _resolve(root, server_name)
    if server is None:
        return {"error": f"no enabled MCP server named '{server_name}'"}
    timeout_f = max(MIN_TIMEOUT, min(MAX_TIMEOUT, float(timeout)))
    if server.get("transport") == "inproc":
        mod_name = server.get("module")
        try:
            mod = importlib.import_module(mod_name) if mod_name else None
        except ImportError as e:
            return {"error": f"cannot import {mod_name}: {e}"}
        if mod is None:
            return {"error": "inproc transport requires 'module'"}
        tools = []
        for attr in dir(mod):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if callable(obj):
                tools.append(
                    {
                        "name": attr,
                        "description": (obj.__doc__ or "").strip().splitlines()[0]
                        if obj.__doc__
                        else "",
                    }
                )
        return {"ok": True, "tools": tools}
    # stdio
    if not server.get("handshake"):
        return {
            "error": "one-shot stdio server has no tools/list; "
            "register with handshake=True to use list_tools()"
        }
    cmd = server.get("command")
    if not cmd:
        return {"error": "stdio transport requires 'command'"}
    try:
        with StdioSession(cmd, env=server.get("env"), timeout=timeout_f) as sess:
            sess.initialize()
            return {
                "ok": True,
                "tools": sess.list_tools(),
                "serverInfo": sess.server_info,
                "capabilities": sess.server_capabilities,
            }
    except FileNotFoundError as e:
        return {"error": f"cannot start MCP server: {e}"}
    except StdioSessionError as e:
        return {"error": str(e)}


def call_tool(
    root: str | os.PathLike,
    server_name: str,
    tool: str,
    args: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    server = _resolve(root, server_name)
    if server is None:
        return {"error": f"no enabled MCP server named '{server_name}'"}
    args = args or {}
    try:
        timeout_f = float(timeout)
    except (TypeError, ValueError):
        timeout_f = 10.0
    timeout_f = max(MIN_TIMEOUT, min(MAX_TIMEOUT, timeout_f))
    if server.get("transport") == "inproc":
        return _call_inproc(server, tool, args)
    return _call_stdio(server, tool, args, timeout_f)
