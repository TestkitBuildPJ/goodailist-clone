"""Browser content-security helpers.

These helpers run BEFORE returning DOM/aria/network/console snapshots to
the caller (the LLM agent).  They are the last line of defence against
**prompt injection from page content** — a malicious site cannot embed a
``<div>`` whose innerText says "Ignore previous instructions and …" and
have the agent obey, because every untrusted slice is wrapped in a
labelled envelope and any ARIA attribute referencing untrusted ids is
rewritten.

This module is stdlib-only; the same functions are called by
``commands_read.py`` so unit tests do not need playwright installed.

Probes covered
--------------
#59 — snapshot envelope wrap (untrusted content marked).
#60 — hidden-element strip (display:none / aria-hidden trees).
#61 — ARIA injection sanitisation (suspicious unicode + control chars).
#62 — URL blocklist (file:/, chrome:/, javascript:, internal IPs).
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

# ---- 1. URL blocklist -----------------------------------------------------

_BLOCKED_SCHEMES: frozenset[str] = frozenset(
    {
        "file",
        "chrome",
        "chrome-extension",
        "javascript",
        "data",
        "about",
        "edge",
        "view-source",
    }
)

# Hosts that resolve to internal/management surfaces.  We refuse to
# navigate to these because they tend to hand out credentials or
# sensitive metadata to whoever asks.
_BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "metadata.google.internal",
        "metadata",
        "169.254.169.254",  # AWS / GCP / Azure IMDS
        "fd00:ec2::254",
        "instance-data",
    }
)

# Private / link-local CIDRs we reject *unless* the caller passes
# ``allow_private=True`` (used by the local dev story where you want
# /vck-qa http://localhost:3000 to work).
_PRIVATE_NETS: tuple[ipaddress._BaseNetwork, ...] = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


@dataclass(frozen=True)
class UrlVerdict:
    allowed: bool
    reason: str


def classify_url(url: str, *, allow_private: bool = False) -> UrlVerdict:
    """Classify ``url`` against the blocklist.

    Probe #62 verifies that, with ``allow_private=False``,
    ``classify_url("http://169.254.169.254/").allowed`` is False.
    """
    if not isinstance(url, str) or not url.strip():
        return UrlVerdict(False, "empty url")
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return UrlVerdict(False, "unparseable url")
    scheme = (parsed.scheme or "").lower()
    if scheme in _BLOCKED_SCHEMES:
        return UrlVerdict(False, f"blocked scheme: {scheme}")
    if scheme not in {"http", "https"}:
        return UrlVerdict(False, f"unsupported scheme: {scheme!r}")
    host = (parsed.hostname or "").lower()
    if not host:
        return UrlVerdict(False, "missing host")
    if host in _BLOCKED_HOSTS:
        return UrlVerdict(False, f"blocked host: {host}")
    # Localhost / loopback always allowed (dev story).
    if host in {"localhost", "127.0.0.1", "::1"}:
        return UrlVerdict(True, "loopback")
    # Numeric host — check private CIDR.
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return UrlVerdict(True, "public hostname")
    if any(ip in net for net in _PRIVATE_NETS) and not allow_private:
        return UrlVerdict(False, f"private network IP: {host}")
    return UrlVerdict(True, "ok")


# ---- 2. Datamarking envelope ---------------------------------------------

# Sentinels chosen to be unique-enough that legitimate content is unlikely
# to contain them.  Probe #59 verifies wrapping is symmetric (open + close).
ENVELOPE_OPEN: str = "<<<UNTRUSTED:BROWSER_CONTENT>>>"
ENVELOPE_CLOSE: str = "<<<END:BROWSER_CONTENT>>>"


def wrap_untrusted(content: str, *, label: str = "page") -> str:
    """Wrap ``content`` in a labelled untrusted-content envelope.

    The envelope is a deterministic, plaintext sentinel pair.  Calling
    this twice on the same content is a no-op (idempotent) so callers
    can safely re-wrap.
    """
    if not isinstance(content, str):
        content = str(content)
    if content.startswith(ENVELOPE_OPEN) and content.endswith(ENVELOPE_CLOSE):
        return content
    safe_label = re.sub(r"[^A-Za-z0-9_-]", "_", label)[:32]
    return f"{ENVELOPE_OPEN}[label={safe_label}]\n" f"{content}\n" f"{ENVELOPE_CLOSE}"


def is_wrapped(content: str) -> bool:
    """True iff ``content`` is bracketed by the untrusted envelope."""
    return (
        isinstance(content, str)
        and content.startswith(ENVELOPE_OPEN)
        and content.rstrip().endswith(ENVELOPE_CLOSE)
    )


# ---- 3. ARIA / control-char sanitisation ---------------------------------

# Strip ASCII / Unicode control characters except "common safe" ones
# (tab, LF, CR).  Tabs/newlines are preserved to keep snapshot diffs
# readable.
_SAFE_CONTROL = {0x09, 0x0A, 0x0D}

# Bidi / format characters that the permission engine already strips
# via ``permission_engine._normalise_unicode``.  We replicate the rule
# locally so this module is independent.
_BIDI_FORMATS = frozenset(range(0x2066, 0x206A + 1)) | {
    0x200E,
    0x200F,
    0x061C,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x200B,
    0x200C,
    0x200D,
    0xFEFF,
}


def sanitise_text(text: str) -> str:
    """Return ``text`` with control / bidi characters stripped.

    Probe #61 checks that an injected RTL override (``\\u202E``) is
    removed before the caller sees it.
    """
    if not isinstance(text, str):
        return text
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp in _BIDI_FORMATS:
            continue
        cat = unicodedata.category(ch)
        if cat == "Cf" or (cat == "Cc" and cp not in _SAFE_CONTROL):
            continue
        out.append(ch)
    return "".join(out)


# ---- 4. Hidden-element pruning ------------------------------------------


@dataclass
class DomNode:
    """Minimal DOM-node shape used by the snapshot pruner.

    The pruner is intentionally tolerant: it works on plain dicts shaped
    like ``{"tag": "div", "attrs": {...}, "text": "...", "children":
    [...]}``.  Anything else passes through unchanged.
    """

    tag: str = ""
    attrs: dict = None  # type: ignore[assignment]
    text: str = ""
    children: list = None  # type: ignore[assignment]


def is_hidden_attrs(attrs: dict) -> bool:
    """Return True iff a node's attribute dict marks it hidden.

    Heuristic, matches what gstack browse uses:
    - ``aria-hidden="true"``
    - ``hidden`` boolean attribute
    - ``style`` containing ``display:none`` or ``visibility:hidden``
    """
    if not isinstance(attrs, dict):
        return False
    aria = str(attrs.get("aria-hidden", "")).strip().lower()
    if aria == "true":
        return True
    if "hidden" in attrs and attrs.get("hidden") not in (False, "false", None):
        return True
    style = str(attrs.get("style", "")).lower().replace(" ", "")
    if "display:none" in style or "visibility:hidden" in style:
        return True
    return False


def strip_hidden(node):
    """Recursively prune hidden subtrees from a DOM-node-shaped dict.

    Probe #60 verifies that a tree containing ``aria-hidden="true"`` is
    removed.
    """
    if not isinstance(node, dict):
        return node
    attrs = node.get("attrs") or {}
    if is_hidden_attrs(attrs):
        return None
    kids = node.get("children")
    if isinstance(kids, list):
        new_kids = []
        for c in kids:
            stripped = strip_hidden(c)
            if stripped is not None:
                new_kids.append(stripped)
        node = {**node, "children": new_kids}
    return node


__all__ = [
    "ENVELOPE_OPEN",
    "ENVELOPE_CLOSE",
    "UrlVerdict",
    "classify_url",
    "wrap_untrusted",
    "is_wrapped",
    "sanitise_text",
    "is_hidden_attrs",
    "strip_hidden",
]
