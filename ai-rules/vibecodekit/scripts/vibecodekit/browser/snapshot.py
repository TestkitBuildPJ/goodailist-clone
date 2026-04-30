"""Page snapshot helpers — ARIA tree + DOM hash + visible-content diff.

A snapshot is the canonical "what does the page look like right now"
artefact returned by ``commands_read.snapshot()``.  It contains:

- ``aria``     — accessibility tree (filtered, normalised, datamarked).
- ``dom_hash`` — short stable hash of the visible DOM (used for diffing).
- ``text``     — visible text content of the page.
- ``console``  — last N console messages.
- ``network``  — last N network requests with method/url/status.
- ``url``      — current URL.

This module is stdlib-only.  It is fed by ``manager.py`` (which uses
playwright) but the snapshot logic itself does not import playwright;
that lets us unit-test the diffing / hashing rules without browser
extras installed.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from . import security


@dataclass
class Snapshot:
    """Canonical browser snapshot record."""

    url: str = ""
    title: str = ""
    aria: list[dict[str, Any]] = field(default_factory=list)
    text: str = ""
    dom_hash: str = ""
    console: list[dict[str, Any]] = field(default_factory=list)
    network: list[dict[str, Any]] = field(default_factory=list)
    captured_ts: float = field(default_factory=time.time)
    protocol_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def _stable_json(obj: Any) -> str:
    """JSON-encode with deterministic key order so the hash is stable."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def hash_dom(dom: Any) -> str:
    """Return a short hex digest of the supplied DOM-shaped object.

    Used by ``commands_read.diff()`` to detect "did the page actually
    change since the last snapshot?" without shipping the full tree.
    """
    blob = _stable_json(dom).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def normalise_aria(tree: Any) -> Any:
    """Recursively prune hidden subtrees and sanitise text.

    Probes #60/#61 verify hidden-strip + control-char strip on the
    snapshot-shaped data the agent eventually sees.
    """
    pruned = security.strip_hidden(tree) if isinstance(tree, dict) else tree
    return _sanitise_recurse(pruned)


def _sanitise_recurse(node: Any) -> Any:
    if isinstance(node, str):
        return security.sanitise_text(node)
    if isinstance(node, dict):
        return {k: _sanitise_recurse(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_sanitise_recurse(v) for v in node]
    return node


def envelope_snapshot(snap: Snapshot) -> dict[str, Any]:
    """Return ``snap`` as a dict, with the text body wrapped untrusted.

    Probe #59 verifies that the returned ``text`` field starts with
    :data:`security.ENVELOPE_OPEN`.
    """
    payload = snap.to_dict()
    payload["text"] = security.wrap_untrusted(snap.text, label="page-text")
    return payload


def diff(prev: Snapshot, curr: Snapshot) -> dict[str, Any]:
    """Compute a coarse diff between two snapshots.

    Returns a dict with ``url_changed``, ``dom_changed``, ``new_console``
    (count), ``new_network`` (count), and ``elapsed_seconds``.
    """
    return {
        "url_changed": prev.url != curr.url,
        "dom_changed": prev.dom_hash != curr.dom_hash,
        "new_console": max(0, len(curr.console) - len(prev.console)),
        "new_network": max(0, len(curr.network) - len(prev.network)),
        "elapsed_seconds": max(0.0, curr.captured_ts - prev.captured_ts),
    }


__all__ = [
    "Snapshot",
    "hash_dom",
    "normalise_aria",
    "envelope_snapshot",
    "diff",
]
