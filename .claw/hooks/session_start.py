#!/usr/bin/env python3
"""session_start hook — emits a banner so the operator knows the overlay
is live, opportunistically refreshes auto-maintained CLAUDE.md
sections (rate-limited so this never spams disk I/O), and injects up
to 10 most-recent learnings so prior project context is visible to
the host LLM at session start (v0.15.0-alpha; opt-out via
``VIBECODE_LEARNINGS_INJECT=0``).
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read_overlay_version() -> str:
    for candidate in (
        os.path.join(_HERE, "..", "..", "VERSION"),
        os.path.join(_HERE, "..", "..", "..", "VERSION"),
    ):
        try:
            with open(candidate, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            continue
    return "unknown"


banner = f"VibecodeKit v{_read_overlay_version()} engaged"
auto_writeback = {"ran": False, "reason": "skipped"}
learnings_inject = {"injected": 0, "reason": "skipped", "items": []}

# Resolve the vibecodekit Python package across known install layouts.
# Order: explicit env override → ai-rules overlay → skill bundle dev → none.
# (v0.16.0 — audit P3 #12: dedup with the module-level ``_HERE`` instead
# of recomputing ``here = os.path.dirname(...)``.)
repo = os.environ.get("CLAW_PROJECT_ROOT") or os.getcwd()
_candidates = [
    os.environ.get("VIBECODEKIT_SKILL_PATH"),
    os.path.join(repo, "ai-rules", "vibecodekit", "scripts"),
    os.path.join(_HERE, "..", "..", "..", "skill", "vibecodekit-hybrid-ultra", "scripts"),
    os.path.join(_HERE, "..", "..", "ai-rules", "vibecodekit", "scripts"),
]
for _cand in _candidates:
    if _cand and os.path.isdir(os.path.join(_cand, "vibecodekit")):
        sys.path.insert(0, os.path.abspath(_cand))
        break

# Best-effort: never let writeback errors block session start.
try:
    from vibecodekit.auto_writeback import try_refresh  # type: ignore

    decision = try_refresh(repo)
    auto_writeback = {
        "ran": decision.ran,
        "reason": decision.reason,
        "elapsed_s": round(decision.elapsed_s, 3),
        "sections_updated": list(decision.sections_updated),
    }
except Exception as exc:  # noqa: BLE001
    auto_writeback = {"ran": False, "reason": f"hook_error: {type(exc).__name__}"}

# v0.15.0-alpha (PR-B / T3) — auto-inject most-recent learnings into
# the session-start payload so the host LLM can surface prior project
# context.  Opt-out with ``VIBECODE_LEARNINGS_INJECT=0``.  Limit
# overridable via ``VIBECODE_LEARNINGS_INJECT_LIMIT`` (default 10).
# Scope filter via ``VIBECODE_LEARNINGS_INJECT_SCOPES`` (comma-separated
# subset of "user,project,team"; default = all scopes).  Failures are
# silent — never break session start.
#
# v0.15.3 (Bug #4) — also emit a ready-to-paste ``addendum`` markdown
# string so hosts that prefer prompt-injection (Claude Code, Cursor)
# don't need to re-format the JSON ``items`` themselves.
if os.environ.get("VIBECODE_LEARNINGS_INJECT", "1") != "0":
    try:
        from vibecodekit.learnings import load_recent, recent_for_prompt  # type: ignore

        _limit_raw = os.environ.get("VIBECODE_LEARNINGS_INJECT_LIMIT", "10")
        try:
            _limit = max(0, int(_limit_raw))
        except ValueError:
            _limit = 10
        _scopes_raw = os.environ.get("VIBECODE_LEARNINGS_INJECT_SCOPES", "")
        _scopes = tuple(s.strip() for s in _scopes_raw.split(",") if s.strip()) or None
        _recent = load_recent(limit=_limit, root=repo, scopes=_scopes)
        _addendum = recent_for_prompt(limit=_limit, scopes=_scopes, root=repo)
        learnings_inject = {
            "injected": len(_recent),
            "reason": "ok",
            "addendum": _addendum,
            "items": [
                {
                    "text": l.text,
                    "scope": l.scope,
                    "tags": list(l.tags),
                    "captured_ts": l.captured_ts,
                }
                for l in _recent
            ],
        }
    except Exception as exc:  # noqa: BLE001
        learnings_inject = {
            "injected": 0,
            "reason": f"hook_error: {type(exc).__name__}",
            "addendum": "",
            "items": [],
        }
else:
    learnings_inject = {"injected": 0, "reason": "opt_out", "addendum": "", "items": []}

sys.stdout.write(
    json.dumps(
        {
            "decision": "allow",
            "banner": banner,
            "auto_writeback": auto_writeback,
            "learnings_inject": learnings_inject,
        }
    )
)
