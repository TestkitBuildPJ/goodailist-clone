"""Bridge between browser commands and the VCK-HU permission engine.

Every browser-level operation (`goto`, `click`, `fill`, `screenshot`, …)
is rendered as a synthetic shell-style command string of the form::

    browser:goto https://example.com
    browser:click [selector="#login"]
    browser:fill   [selector="#email" value="<redacted>"]

The string is then handed to ``permission_engine.classify_cmd`` which
applies the same Unicode-normalisation, denial-store lookup, and
permission-class assignment used by every other command in the system.
This guarantees probe #58: **no browser command bypasses the permission
pipeline**.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Late import inside functions so this module stays light on import.
# (Avoids importing the heavy ``permission_engine`` graph for unit tests
# that only care about the surface API of the browser package.)


def render_browser_command(
    verb: str, target: str | None = None, extras: Mapping[str, Any] | None = None
) -> str:
    """Return the canonical ``browser:<verb> <target> [k=v ...]`` string.

    The serialised form is what the permission engine sees and audits.
    """
    if not isinstance(verb, str) or not verb.strip():
        raise ValueError("verb must be a non-empty string")
    parts = [f"browser:{verb.strip()}"]
    if target:
        parts.append(str(target))
    if extras:
        kv_bits = []
        for k in sorted(extras):
            v = extras[k]
            kv_bits.append(f"{k}={v!r}")
        parts.append("[" + " ".join(kv_bits) + "]")
    return " ".join(parts)


def classify(verb: str, target: str | None = None, extras: Mapping[str, Any] | None = None):
    """Classify a browser operation through the permission engine.

    Returns the ``(class, reason)`` tuple from
    ``permission_engine.classify_cmd``.  Caller is expected to honour
    the verdict (e.g. bubble-escalate on ``mutation``/``high_risk``,
    refuse on ``blocked``).
    """
    from .. import permission_engine as pe  # type: ignore

    cmd = render_browser_command(verb, target, extras)
    classify_fn = getattr(pe, "classify_cmd", None)
    if classify_fn is None:
        raise RuntimeError(
            "permission_engine.classify_cmd is unavailable; cannot "
            "classify browser command — refusing to fall back to "
            "an unguarded execution path"
        )
    return classify_fn(cmd)


__all__ = ["render_browser_command", "classify"]
