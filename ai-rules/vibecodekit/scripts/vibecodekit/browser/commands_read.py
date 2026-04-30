"""Read-only browser commands.

Each command corresponds to one CLI verb (``text``, ``html``, ``links``,
``forms``, ``aria``, ``console``, ``network``, ``snapshot``) and goes
through three layers:

    1. ``permission.classify(verb, target, extras)`` — through the
       permission engine.  Class verdict is recorded.
    2. ``manager.with_page()`` — invokes Playwright to execute the
       observation.  This layer is in :mod:`vibecodekit.browser.manager`
       and only loads when ``[browser]`` extras are installed.
    3. ``security.wrap_untrusted`` / ``snapshot.normalise_aria`` —
       envelope wrap + hidden strip before returning to the agent.

This module is stdlib-only — the layers 1 and 3 are pure-Python and the
manager hand-off is dynamic, so unit tests can exercise the permission
+ envelope behaviour without playwright installed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from . import permission, security
from . import snapshot as snap_mod


# Each verb declares (a) whether it is fundamentally read-only, and (b)
# whether the resulting payload is "untrusted page content" that must be
# envelope-wrapped before returning to the agent.
@dataclass(frozen=True)
class ReadVerb:
    name: str
    untrusted_payload: bool = True


VERBS: tuple[ReadVerb, ...] = (
    ReadVerb("text"),
    ReadVerb("html"),
    ReadVerb("links"),
    ReadVerb("forms"),
    ReadVerb("aria"),
    ReadVerb("console", untrusted_payload=True),
    ReadVerb("network", untrusted_payload=True),
    ReadVerb("snapshot"),
    # Verbs whose response is daemon-internal (not page-derived) do not
    # need envelope wrap — but they still go through permission.
    ReadVerb("status", untrusted_payload=False),
    ReadVerb("tabs", untrusted_payload=False),
)
_VERBS_BY_NAME = {v.name: v for v in VERBS}


def is_known_read_verb(name: str) -> bool:
    return name in _VERBS_BY_NAME


def execute(
    verb: str,
    target: str | None = None,
    extras: Mapping[str, Any] | None = None,
    *,
    runner: Callable[[str, str | None, Mapping[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Run a read-only browser verb end-to-end.

    Parameters
    ----------
    verb
        One of :data:`VERBS`.
    target
        URL / selector / verb-specific argument.
    extras
        Verb-specific kwargs.
    runner
        Callable that executes the verb against the daemon.  Defaults to
        :func:`_default_runner` which dynamically imports
        :mod:`vibecodekit.browser.manager` (browser extras required).
        Tests inject a stub.

    Returns
    -------
    dict
        ``{"verb", "klass", "reason", "payload"}`` — ``payload`` is
        envelope-wrapped if the verb's :attr:`ReadVerb.untrusted_payload`
        is True.
    """
    extras_dict: dict[str, Any] = dict(extras or {})
    if not is_known_read_verb(verb):
        raise ValueError(f"unknown read verb: {verb!r}")
    spec = _VERBS_BY_NAME[verb]

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

    payload: Any
    if spec.untrusted_payload:
        if verb == "snapshot" and isinstance(raw, snap_mod.Snapshot):
            payload = snap_mod.envelope_snapshot(raw)
        else:
            payload = security.wrap_untrusted(_stringify(raw), label=f"page-{verb}")
    else:
        payload = raw

    return {
        "verb": verb,
        "klass": klass,
        "reason": reason,
        "payload": payload,
    }


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    try:
        import json as _json

        return _json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    except Exception:
        return str(value)


def _default_runner(verb: str, target: str | None, extras: Mapping[str, Any]) -> Any:
    """Default runner — delegates to the playwright-backed manager.

    Lazily imported so this module remains stdlib-only at import time.
    """
    from . import manager  # type: ignore  # imports only when extras installed

    return manager.run_read_verb(verb, target, dict(extras))


__all__ = ["VERBS", "ReadVerb", "is_known_read_verb", "execute"]
