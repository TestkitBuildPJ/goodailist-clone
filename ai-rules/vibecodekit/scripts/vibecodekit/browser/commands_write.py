"""Imperative (write) browser commands.

Verbs that **mutate the page or browser state** — ``goto``, ``click``,
``fill``, ``select``, ``scroll``, ``wait_for``, ``screenshot``,
``set_cookie``, ``new_tab``, ``close_tab``.  Like
:mod:`commands_read`, each verb passes through the permission engine
and the runner is a swappable callable so tests do not need playwright.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from . import permission, security


@dataclass(frozen=True)
class WriteVerb:
    name: str
    needs_url: bool = False
    high_risk: bool = False


VERBS: tuple[WriteVerb, ...] = (
    WriteVerb("goto", needs_url=True),
    WriteVerb("click"),
    WriteVerb("fill"),
    WriteVerb("select"),
    WriteVerb("scroll"),
    WriteVerb("wait_for"),
    WriteVerb("screenshot"),
    WriteVerb("set_cookie", high_risk=True),
    WriteVerb("new_tab"),
    WriteVerb("close_tab"),
)
_VERBS_BY_NAME = {v.name: v for v in VERBS}


def is_known_write_verb(name: str) -> bool:
    return name in _VERBS_BY_NAME


def execute(
    verb: str,
    target: str | None = None,
    extras: Mapping[str, Any] | None = None,
    *,
    runner: Callable[[str, str | None, Mapping[str, Any]], Any] | None = None,
    allow_private: bool = False,
) -> dict[str, Any]:
    """Run a write browser verb end-to-end.

    For ``goto`` (and any verb with ``needs_url=True``) the target is
    classified through :func:`security.classify_url` before the
    permission engine sees it — so a request to
    ``http://169.254.169.254/`` is refused even if the permission engine
    would otherwise accept the synthetic command.
    """
    extras_dict: dict[str, Any] = dict(extras or {})
    if not is_known_write_verb(verb):
        raise ValueError(f"unknown write verb: {verb!r}")
    spec = _VERBS_BY_NAME[verb]

    if spec.needs_url:
        if not target:
            return {
                "verb": verb,
                "klass": "blocked",
                "reason": f"{verb} requires a URL target",
                "payload": None,
            }
        verdict = security.classify_url(target, allow_private=allow_private)
        if not verdict.allowed:
            return {
                "verb": verb,
                "klass": "blocked",
                "reason": f"url policy: {verdict.reason}",
                "payload": None,
            }

    klass, reason = permission.classify(verb, target, extras_dict)
    if klass == "blocked":
        return {
            "verb": verb,
            "klass": klass,
            "reason": reason,
            "payload": None,
        }

    runner = runner or _default_runner
    raw = runner(verb, target, extras_dict)

    return {
        "verb": verb,
        "klass": klass,
        "reason": reason,
        "payload": raw,
    }


def _default_runner(verb: str, target: str | None, extras: Mapping[str, Any]) -> Any:
    """Default runner — delegates to the playwright-backed manager."""
    from . import manager  # type: ignore  # imports only when extras installed

    return manager.run_write_verb(verb, target, dict(extras))


__all__ = ["VERBS", "WriteVerb", "is_known_write_verb", "execute"]
