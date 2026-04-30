"""Hook interceptor — Pattern #14 (lifecycle hooks).

v0.7 fixes two bugs from v0.6:

1.  Hook scripts now receive the triggering command on **argv** as well as via
    ``$VIBECODE_HOOK_COMMAND``.  v0.6 passed nothing, which silently neutered
    the shipped ``pre_tool_guard.sh`` guard.
2.  A hook may return a JSON object on stdout; if present, the runtime uses
    the ``decision`` field (``allow`` | ``deny`` | ``rewrite``) instead of
    inferring from the exit code.  This matches Claude Code's rich hook
    protocol (Giải phẫu §10.3).

Sandbox:  by default, hooks inherit a *filtered* environment that strips any
variable whose name matches ``*TOKEN*`` / ``*KEY*`` / ``*SECRET*`` /
``*PASSWORD*`` (case-insensitive).  Set ``VIBECODE_HOOK_ALLOW_SECRETS=1`` in
the parent process to disable this (not recommended).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ._logging import get_logger

_log = get_logger("vibecodekit.hook_interceptor")

# 26 lifecycle events mirroring Claude Code (Giải phẫu §10.3).  Event names
# use snake_case (Python convention); their Claude Code counterparts are
# documented in references/14-plugin-extension.md.
SUPPORTED_EVENTS = (
    # Tool lifecycle (3)
    "pre_tool_use",
    "post_tool_use",
    "post_tool_use_failure",
    # Permission (2)
    "permission_denied",
    "permission_request",
    # Session (3)
    "session_start",
    "session_end",
    "setup",
    # Agent lifecycle (3)
    "subagent_start",
    "subagent_stop",
    "teammate_idle",
    # Task (4)
    "task_created",
    "task_completed",
    "stop",
    "stop_failure",
    # Context (3)
    "pre_compact",
    "post_compact",
    "notification",
    # Filesystem (4)
    "file_changed",
    "cwd_changed",
    "worktree_create",
    "worktree_remove",
    # UI / Config (5)
    "elicitation",
    "elicitation_result",
    "config_change",
    "instructions_loaded",
    "user_prompt_submit",
    # Query (legacy VibecodeKit-specific; kept for back-compat)
    "pre_query",
    "post_query",
    "pre_tip",
    "post_completion",
    "pre_release",
    "pre_release_gate",
)

_SECRET_RX = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|PASSWD|PRIVATE|CREDENTIAL)", re.IGNORECASE)
_HOOK_TIMEOUT = 30

# Patterns that mark a value as secret regardless of the key.  Entries are
# ``(regex, kind)``:
#   kind == "prefix"   → preserve the regex's group(1) (a prefix like
#                        "Authorization: Bearer ") and redact the tail
#   kind == "whole"    → replace the whole match with "***REDACTED***"
# This avoids accidentally re-emitting the secret when the pattern's
# capturing group *is* the secret (e.g. AWS keys).
_VALUE_SECRET_PATTERNS = [
    (re.compile(r"(Authorization:\s*Bearer\s+)\S+", re.IGNORECASE), "prefix"),
    (re.compile(r"(Authorization:\s*Basic\s+)\S+", re.IGNORECASE), "prefix"),
    (
        re.compile(
            r"(--?(?:password|pw|pwd|token|apikey|api-key|secret)[= ])\s*\S+", re.IGNORECASE
        ),
        "prefix",
    ),
    # AWS / OpenAI / GitHub / GitLab token shapes — whole match:
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "whole"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "whole"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "whole"),
    (re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), "whole"),  # GitHub PAT
    (re.compile(r"\bghs_[A-Za-z0-9]{30,}\b"), "whole"),
    (re.compile(r"\bgho_[A-Za-z0-9]{30,}\b"), "whole"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "whole"),
    # Generic high-entropy hex ≥ 48 chars.
    # 40-hex exactly would also hit git SHAs (false positive, v0.10.1 fix);
    # raising the lower bound to 48 skips SHA-1 while still catching
    # SHA-256 / slack webhook / google key style secrets.
    (re.compile(r"\b[a-f0-9]{48,}\b"), "whole"),
]


def _filter_env(env: dict[str, str]) -> dict[str, str]:
    if os.environ.get("VIBECODE_HOOK_ALLOW_SECRETS") == "1":
        return env
    filtered = {k: v for k, v in env.items() if not _SECRET_RX.search(k)}
    dropped = len(env) - len(filtered)
    if dropped:
        _log.info("hook_env_scrubbed", extra={"dropped_count": dropped})
    return filtered


def _scrub_str(text: str) -> str:
    """Redact likely secrets in free-form strings (e.g. bash commands)."""
    if os.environ.get("VIBECODE_HOOK_ALLOW_SECRETS") == "1":
        return text
    out = text
    for rx, kind in _VALUE_SECRET_PATTERNS:
        if kind == "prefix":
            out = rx.sub(lambda m: m.group(1) + "***REDACTED***", out)
        else:
            out = rx.sub("***REDACTED***", out)
    return out


def _scrub_payload(obj: Any) -> Any:
    """Recursively scrub a payload: keys matching ``_SECRET_RX`` → redacted,
    string values passed through ``_scrub_str``."""
    if os.environ.get("VIBECODE_HOOK_ALLOW_SECRETS") == "1":
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_RX.search(k):
                out[k] = "***REDACTED***"
            else:
                out[k] = _scrub_payload(v)
        return out
    if isinstance(obj, list):
        return [_scrub_payload(x) for x in obj]
    if isinstance(obj, str):
        return _scrub_str(obj)
    return obj


def _hook_cmd(hook: Path, command_repr: str) -> list[str]:
    if hook.suffix == ".py":
        return ["python3", str(hook), command_repr]
    return ["bash", str(hook), command_repr]


def run_hooks(
    root: str | os.PathLike, event: str, payload: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    root = Path(root)
    hooks_dir = root / ".claw" / "hooks"
    if not hooks_dir.exists():
        return []
    results: list[dict[str, Any]] = []
    # Sanitise payload and command before exposing either to third-party hooks.
    clean_payload = _scrub_payload(payload or {})
    command_repr = _scrub_str(str(clean_payload.get("command") or ""))
    env = _filter_env(os.environ.copy())
    env["VIBECODE_HOOK_EVENT"] = event
    env["VIBECODE_HOOK_PAYLOAD"] = json.dumps(clean_payload, ensure_ascii=False)
    env["VIBECODE_HOOK_COMMAND"] = command_repr

    for suffix in (".py", ".sh"):
        hook = hooks_dir / f"{event}{suffix}"
        if not hook.exists():
            continue
        if not os.access(hook, os.X_OK):
            # Make non-executable hooks runnable implicitly (common mistake).
            try:
                hook.chmod(0o755)
            except OSError:
                pass
        try:
            p = subprocess.run(
                _hook_cmd(hook, command_repr),
                cwd=str(root),
                env=env,
                text=True,
                capture_output=True,
                timeout=_HOOK_TIMEOUT,
            )
            stdout = (p.stdout or "")[-4000:]
            stderr = (p.stderr or "")[-4000:]
            decision = None
            try:
                parsed = json.loads(stdout.strip()) if stdout.strip().startswith("{") else None
                if isinstance(parsed, dict):
                    decision = parsed.get("decision")
            except json.JSONDecodeError:
                parsed = None
            results.append(
                {
                    "hook": str(hook.relative_to(root)),
                    "event": event,
                    "returncode": p.returncode,
                    "decision": decision,
                    "stdout": stdout,
                    "stderr": stderr,
                    "structured": parsed,
                }
            )
        except subprocess.TimeoutExpired as e:
            results.append(
                {
                    "hook": str(hook),
                    "event": event,
                    "returncode": 124,
                    "error": f"timeout after {_HOOK_TIMEOUT}s",
                    "stdout": (e.stdout or "")[-4000:],
                    "stderr": (e.stderr or "")[-4000:],
                }
            )
        except Exception as e:  # pragma: no cover
            results.append({"hook": str(hook), "event": event, "returncode": 99, "error": str(e)})
    return results


def is_blocked(results: Iterable[dict[str, Any]]) -> bool:
    for r in results:
        if r.get("decision") == "deny":
            return True
        rc = r.get("returncode")
        if rc is not None and rc != 0 and r.get("decision") != "allow":
            return True
    return False
