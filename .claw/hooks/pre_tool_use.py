#!/usr/bin/env python3
"""pre_tool_use hook — permission-check shell commands.

Only ``run_command`` (a.k.a. bash) invocations are routed through the
6-layer permission engine.  Every other tool (list_files, read_file, grep,
glob, write_file, append_file) has its own safety gates in
``tool_executor.py`` and is auto-allowed here — otherwise we'd deny
every benign read in the query loop (v0.7.0 bug).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "ai-rules", "vibecodekit", "scripts"))
if os.path.isdir(SCRIPTS):
    sys.path.insert(0, SCRIPTS)


def _payload() -> dict:
    raw = os.environ.get("VIBECODE_HOOK_PAYLOAD", "{}") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


payload = _payload()
tool = payload.get("tool") or ""
cmd = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VIBECODE_HOOK_COMMAND", "")
mode = os.environ.get("VIBECODE_PERMISSION_MODE", "default")
touched = payload.get("path") or payload.get("file") or ""

# v0.11.3 / Patch C — emit a non-blocking ``skill_activation`` signal so
# the host (Claude Code / Devin / Cursor) can lazy-load this skill when
# the user touches a file matching SKILL.md ``paths:`` globs.  The
# signal is advisory — pre_tool_use must not block for it.
skill_activation = None
if touched:
    try:
        from vibecodekit.skill_discovery import activate_for as _activate_for

        skill_activation = _activate_for(touched)
    except Exception as exc:  # noqa: BLE001
        skill_activation = {"activate": False, "reason": f"hook_error: {type(exc).__name__}"}

if tool != "run_command" or not cmd:
    out = {
        "decision": "allow",
        "reason": f"{tool or 'unknown'}: non-shell tool (handled by tool_executor)",
    }
    if skill_activation is not None:
        out["skill_activation"] = skill_activation
    sys.stdout.write(json.dumps(out))
    sys.exit(0)

try:
    from vibecodekit.permission_engine import decide
except Exception as e:
    out = {"decision": "allow", "reason": f"engine unavailable: {e}"}
    if skill_activation is not None:
        out["skill_activation"] = skill_activation
    sys.stdout.write(json.dumps(out))
    sys.exit(0)

decision = decide(cmd, mode=mode)

# v0.15.0-alpha (PR-B) — security classifier is **auto-on by default**.
# The regex layer is stdlib-only and the optional ONNX / Haiku layers
# self-disable when their deps / env vars are missing, so this is safe
# to run unconditionally.  Operators who need the old v0.14.x opt-in
# semantics can disable with ``VIBECODE_SECURITY_CLASSIFIER=0``.  Even
# a pure-regex ensemble can upgrade an "allow" to "deny" when a prompt
# injection or secret-leak pattern matches.  The try-block below makes
# any unexpected error non-fatal so the permission path is never
# interrupted.
if os.environ.get("VIBECODE_SECURITY_CLASSIFIER", "1") != "0":
    try:
        from vibecodekit.security_classifier import load_default_classifier

        _res = load_default_classifier().classify(cmd)
        if _res.verdict.decision == "deny":
            decision = {
                "decision": "deny",
                "reason": f"security_classifier: {_res.verdict.reason}",
                "classifier": _res.as_dict(),
            }
        else:
            decision.setdefault("classifier", _res.as_dict())
    except Exception as exc:  # pragma: no cover — never break the hook
        decision.setdefault("classifier_error", f"{type(exc).__name__}: {exc}")

if skill_activation is not None:
    decision["skill_activation"] = skill_activation
sys.stdout.write(json.dumps(decision))
sys.exit(0)
