"""VCK-HU browser daemon — Python-pure sub-second real-browser QA layer.

Architecture inspired by gstack's `browse/` daemon (Bun + Playwright + atomic
state file + idle-timeout); reimplemented in Python so it integrates natively
with VCK-HU's permission engine, denial store, and conformance audit.

Public surface
--------------
- :mod:`vibecodekit.browser.state`  — atomic state file (port + pid + idle).
- :mod:`vibecodekit.browser.security` — datamarking / ARIA wrap / URL blocklist.
- :mod:`vibecodekit.browser.permission` — bridge to ``permission_engine``.
- :mod:`vibecodekit.browser.snapshot` — ARIA-tree + DOM hash + visible-diff helpers.
- :mod:`vibecodekit.browser.cli_adapter` — CLI ↔ daemon HTTP client.
- :mod:`vibecodekit.browser.commands_read` — descriptive (read-only) operations.
- :mod:`vibecodekit.browser.commands_write` — imperative (write) operations.
- :mod:`vibecodekit.browser.manager`  — Playwright lifecycle (browser extras).
- :mod:`vibecodekit.browser.server`   — FastAPI process (browser extras).

The ``manager`` and ``server`` modules require the ``[browser]`` optional
extras (``playwright``, ``fastapi``, ``uvicorn``, ``httpx``).  The other
modules are stdlib-only so they can be unit-tested without any extras
installed — preserving VCK-HU's stdlib-only DNA for the *core* and only
introducing third-party deps when the user explicitly opts in.

Attribution
-----------
Architecture (FastAPI/Bun.serve persistent daemon + Playwright/CDP +
atomic state file with idle-timeout + permission-classified commands +
ARIA datamarking envelope) inspired by gstack/browse @ commit 675717e3.
Implementation is a clean-room rewrite — no source code copied.  See
``LICENSE-third-party.md``.
"""

from __future__ import annotations

from . import cli_adapter as cli_adapter  # noqa: F401
from . import commands_read as commands_read  # noqa: F401
from . import commands_write as commands_write  # noqa: F401
from . import permission as permission  # noqa: F401
from . import security as security  # noqa: F401
from . import snapshot as snapshot  # noqa: F401

# Sub-modules that are stdlib-only; safe to import even without extras.
from . import state as state  # noqa: F401

__all__ = [
    "state",
    "security",
    "permission",
    "snapshot",
    "commands_read",
    "commands_write",
    "cli_adapter",
]

# Browser-daemon protocol version — bumped when wire format changes so
# the CLI client and server can refuse mismatched daemons.
PROTOCOL_VERSION = "1.0.0"
