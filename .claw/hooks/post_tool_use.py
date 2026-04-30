#!/usr/bin/env python3
"""post_tool_use hook — append the result summary to the session event bus
and, when ``VIBECODE_AUTOCOMMIT=1`` is set, drive the policy decision in
:mod:`vibecodekit.auto_commit_hook`.

This is the wiring point promised in ``USAGE_GUIDE.md §16.5`` (audit
finding P2 #6 + P2 #7, ``docs/audits/v0.15.4-recheck.md``).  Importing
``auto_commit_hook`` here also fulfils the no-orphan-module probe (#85)
without an allowlist entry — the hook is the production call site.

Design invariants (so this hook is safe by default):

1. **Hook output never changes.**  The stdout JSON envelope is always
   ``{"decision": "allow", ...}`` regardless of whether the auto-commit
   policy succeeded, deferred, or refused.  Down-stream
   ``hook_interceptor`` parsing logic is unchanged.

2. **Auto-commit is opt-in.**  The bundled :class:`AutoCommitHook` defaults
   to *opt-in* (run unless ``VIBECODE_NO_AUTOCOMMIT=1`` /
   ``VIBECODE_AUTOCOMMIT=0`` is set).  We invert that here: the hook only
   asks ``AutoCommitHook`` to run when ``VIBECODE_AUTOCOMMIT=1`` is
   explicitly present, so dropping the overlay into a project never
   surprises the operator with unsolicited commits.

3. **Failures are swallowed.**  Any import error, git error, or policy
   refusal is recorded in the JSON envelope's ``auto_commit`` field; it
   never raises and never flips ``decision`` away from ``allow``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _autocommit_enabled() -> bool:
    """Auto-commit is *off* by default in the hook context.

    The bundled :class:`AutoCommitHook` is opt-in by default, but its
    semantics are designed for explicit Python API callers.  When the
    overlay is dropped into an arbitrary project we want the safer
    inverted default — explicit env var to enable.
    """
    return os.environ.get("VIBECODE_AUTOCOMMIT") == "1"


def _maybe_autocommit(payload: dict) -> dict:
    """Drive :class:`vibecodekit.auto_commit_hook.AutoCommitHook` when
    enabled.  Returns a JSON-serialisable summary for the envelope."""
    if not _autocommit_enabled():
        return {"ran": False, "reason": "VIBECODE_AUTOCOMMIT != '1'"}
    try:
        # Imported lazily so the hook still works inside install-only
        # environments where the bundle's scripts/ directory isn't on
        # sys.path (e.g. early-stage scaffold runs).
        from vibecodekit.auto_commit_hook import AutoCommitHook  # noqa: WPS433
    except ImportError as exc:
        return {"ran": False, "reason": f"import failed: {exc!r}"}

    repo = Path(os.environ.get("VIBECODE_PROJECT_ROOT") or os.getcwd()).resolve()
    debounce_s = float(os.environ.get("VIBECODE_AUTOCOMMIT_DEBOUNCE_S") or 60.0)
    message_prefix = os.environ.get("VIBECODE_AUTOCOMMIT_PREFIX") or "[vibecode-auto]"

    tool = str(payload.get("tool") or "post_tool_use")
    try:
        hook = AutoCommitHook(debounce_s=debounce_s, message_prefix=message_prefix)
        decision = hook.commit(repo, message=f"after {tool}")
    except Exception as exc:  # never raise out of a hook
        return {"ran": False, "reason": f"commit raised: {exc!r}"}

    return {
        "ran": True,
        "committed": bool(decision.commit),
        "reason": decision.reason,
        "files": list(decision.files),
        "debounced_remaining_s": round(decision.debounced_remaining_s, 3),
    }


def main() -> int:
    payload_raw = os.environ.get("VIBECODE_HOOK_PAYLOAD", "{}") or "{}"
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        payload = {}

    summary = {
        "decision": "allow",
        "observed_tool": payload.get("tool"),
        "auto_commit": _maybe_autocommit(payload),
    }
    sys.stdout.write(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
