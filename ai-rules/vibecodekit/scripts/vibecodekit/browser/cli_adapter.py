"""CLI ↔ daemon HTTP client adapter.

Provides a tiny synchronous client that the user-facing
``vibecodekit.cli browser …`` subcommand uses to dispatch verbs to the
running browser daemon.  When the daemon is not running, the adapter
auto-spawns one (by execing ``python -m vibecodekit.browser.server``)
and waits up to ``BOOT_TIMEOUT_SECONDS`` for the state file to appear
with a live PID.

The HTTP plumbing intentionally uses ``urllib`` from the stdlib rather
than ``httpx`` so this client module remains import-safe without the
``[browser]`` extras installed.  (The *server* still needs FastAPI +
uvicorn, but those only load on the daemon side.)
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import state as state_mod

BOOT_TIMEOUT_SECONDS: float = 10.0
HTTP_TIMEOUT_SECONDS: float = 30.0


@dataclass
class DaemonClient:
    """Synchronous HTTP client to a running browser daemon."""

    state_file: Path | None = None
    timeout: float = HTTP_TIMEOUT_SECONDS

    def _state(self) -> state_mod.BrowserState:
        s = state_mod.read_state(path=self.state_file)
        if s is None or s.port <= 0 or not state_mod.is_pid_alive(s.pid):
            raise DaemonNotRunning(
                "no live browser daemon found in "
                f"{self.state_file or state_mod.state_path()}; "
                "start one with `python -m vibecodekit.browser.server`"
            )
        return s

    def health(self) -> dict[str, Any]:
        s = self._state()
        return self._get(s.port, "/health")

    def command(
        self, verb: str, target: str | None = None, extras: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        s = self._state()
        body = {
            "verb": verb,
            "target": target,
            "extras": dict(extras or {}),
        }
        return self._post(s.port, "/command", body)

    def shutdown(self) -> dict[str, Any]:
        s = self._state()
        try:
            return self._post(s.port, "/shutdown", {})
        except DaemonHttpError:
            # Daemon may have already exited; clear state to be tidy.
            state_mod.clear_state(path=self.state_file)
            return {"status": "already_stopped"}

    def _get(self, port: int, path: str) -> dict[str, Any]:
        url = f"http://127.0.0.1:{port}{path}"
        req = urllib.request.Request(url, method="GET")
        return self._send(req)

    def _post(self, port: int, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"http://127.0.0.1:{port}{path}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"content-type": "application/json"},
        )
        return self._send(req)

    def _send(self, req: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise DaemonHttpError(f"daemon HTTP error: {e}") from e
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise DaemonHttpError(f"daemon returned non-JSON: {raw[:120]!r}") from e


class DaemonNotRunning(RuntimeError):
    pass


class DaemonHttpError(RuntimeError):
    pass


def is_daemon_alive(state_file: Path | None = None) -> bool:
    """Return True iff there is a live daemon recorded in the state file."""
    s = state_mod.read_state(path=state_file)
    return s is not None and s.port > 0 and state_mod.is_pid_alive(s.pid)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint — ``python -m vibecodekit.browser.cli_adapter <verb> …``.

    This is the minimal CLI surface required by ``/vck-qa``.  The full
    `vibe browser …` command (with auto-spawn, idle management, and
    streaming output) is wired up in :mod:`vibecodekit.cli`.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_usage(), file=sys.stderr)
        return 2

    verb = args[0]
    target = args[1] if len(args) > 1 else None
    extras: dict[str, Any] = {}
    for kv in args[2:]:
        if "=" in kv:
            k, _, v = kv.partition("=")
            extras[k.strip()] = v.strip()

    client = DaemonClient()
    try:
        if verb == "health":
            out = client.health()
        elif verb == "shutdown":
            out = client.shutdown()
        else:
            out = client.command(verb, target, extras)
    except DaemonNotRunning as e:
        print(f"[daemon] {e}", file=sys.stderr)
        return 3
    except DaemonHttpError as e:
        print(f"[daemon] {e}", file=sys.stderr)
        return 4
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _usage() -> str:
    return (
        "usage: python -m vibecodekit.browser.cli_adapter <verb> [target] "
        "[k=v ...]\n"
        "       verbs: health | shutdown | goto | click | fill | text | "
        "html | links | forms | aria | console | network | snapshot | "
        "screenshot | scroll | wait_for | tabs | new_tab | close_tab"
    )


__all__ = [
    "DaemonClient",
    "DaemonNotRunning",
    "DaemonHttpError",
    "BOOT_TIMEOUT_SECONDS",
    "HTTP_TIMEOUT_SECONDS",
    "is_daemon_alive",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
