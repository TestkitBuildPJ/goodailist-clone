"""FastAPI daemon — exposes the browser manager over local HTTP.

The daemon binds to ``127.0.0.1:<random_port>`` and writes the port +
PID to ``~/.vibecode/browser.json`` (mode 0o600, atomic) so the CLI
client can find it.  After ``DEFAULT_IDLE_TIMEOUT_SECONDS`` of
inactivity the daemon shuts itself down gracefully.

Like :mod:`manager`, this module **only loads under the ``[browser]``
extras** (it imports ``fastapi``).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover — exercised only with [browser] extras installed.
    import uvicorn  # type: ignore[import-not-found]
    from fastapi import FastAPI, HTTPException  # type: ignore[import-not-found]
    from pydantic import BaseModel  # type: ignore[import-not-found]
except ModuleNotFoundError as e:  # pragma: no cover
    raise ModuleNotFoundError(
        "vibecodekit.browser.server requires the [browser] extras. "
        "Install with: pip install 'vibecodekit-hybrid-ultra[browser]'"
    ) from e

from . import (
    PROTOCOL_VERSION,
    commands_read,
    commands_write,
)
from . import (
    manager as manager_mod,
)
from . import (
    state as state_mod,
)


class CommandRequest(BaseModel):  # pragma: no cover
    verb: str
    target: str | None = None
    extras: dict[str, Any] | None = None


def create_app(
    *,
    headless: bool = True,
    idle_timeout_seconds: int = state_mod.DEFAULT_IDLE_TIMEOUT_SECONDS,
    state_file: Path | None = None,
) -> FastAPI:  # pragma: no cover
    """Build the FastAPI app.  Used by ``main`` and by tests."""
    app = FastAPI(title="vibecodekit-browser-daemon", version=PROTOCOL_VERSION)
    started = time.time()

    @app.get("/health")
    def health() -> dict[str, Any]:
        state_mod.touch_state(path=state_file)
        return {
            "status": "ok",
            "protocol": PROTOCOL_VERSION,
            "uptime_seconds": time.time() - started,
            "idle_timeout_seconds": idle_timeout_seconds,
        }

    @app.get("/status")
    def status() -> dict[str, Any]:
        state_mod.touch_state(path=state_file)
        return commands_read.execute("status")

    @app.post("/command")
    def command(req: CommandRequest) -> dict[str, Any]:
        state_mod.touch_state(path=state_file)
        verb = req.verb
        target = req.target
        extras = req.extras or {}
        if commands_read.is_known_read_verb(verb):
            return commands_read.execute(verb, target, extras)
        if commands_write.is_known_write_verb(verb):
            return commands_write.execute(
                verb,
                target,
                extras,
                allow_private=bool(extras.get("allow_private", True)),
            )
        raise HTTPException(status_code=400, detail=f"unknown verb: {verb!r}")

    @app.post("/shutdown")
    def shutdown() -> dict[str, Any]:
        state_mod.clear_state(path=state_file)
        manager_mod.stop_manager()
        # Schedule process exit a beat after the response is sent.
        threading.Timer(0.2, lambda: os._exit(0)).start()
        return {"status": "stopping"}

    return app


def _idle_watchdog(idle_timeout_seconds: int, state_file: Path | None) -> None:  # pragma: no cover
    """Background thread that exits the process if idle past timeout."""
    while True:
        time.sleep(max(1, idle_timeout_seconds // 4))
        cur = state_mod.read_state(path=state_file)
        if cur is None:
            continue
        if state_mod.is_idle_expired(cur):
            manager_mod.stop_manager()
            state_mod.clear_state(path=state_file)
            os._exit(0)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    """Daemon entrypoint — ``python -m vibecodekit.browser.server``."""
    p = argparse.ArgumentParser(prog="vibecodekit.browser.server")
    p.add_argument("--port", type=int, default=0, help="Bind port (0 = pick random)")
    p.add_argument("--idle-timeout", type=int, default=state_mod.DEFAULT_IDLE_TIMEOUT_SECONDS)
    p.add_argument("--headless", action="store_true", default=True)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    args = p.parse_args(argv)

    port = args.port if args.port > 0 else state_mod.select_port()
    state = state_mod.BrowserState(
        pid=os.getpid(),
        port=port,
        started_ts=time.time(),
        last_activity_ts=time.time(),
        idle_timeout_seconds=int(args.idle_timeout),
        protocol_version=PROTOCOL_VERSION,
    )
    state_mod.write_state(state)
    print(
        f"[vibecodekit.browser] listening on 127.0.0.1:{port} "
        f"(pid={os.getpid()}, idle_timeout={args.idle_timeout}s)",
        file=sys.stderr,
    )

    t = threading.Thread(
        target=_idle_watchdog,
        args=(int(args.idle_timeout), None),
        daemon=True,
    )
    t.start()

    app = create_app(
        headless=args.headless,
        idle_timeout_seconds=int(args.idle_timeout),
    )

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    finally:
        state_mod.clear_state()
        manager_mod.stop_manager()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
