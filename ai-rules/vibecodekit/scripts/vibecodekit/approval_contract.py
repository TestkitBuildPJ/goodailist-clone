"""Approval / elicitation UI contract — Giải phẫu §10.4.

Claude Code uses a *structured JSON contract* to surface permission
requests, dangerous diffs, and other human-in-the-loop decisions to
whatever UI is driving it (CLI, VS Code, web).  The contract is:

    {
      "kind":    "permission" | "diff" | "elicitation" | "notification",
      "title":   str,
      "summary": str,                 # short one-liner
      "risk":    "low" | "medium" | "high" | "critical",
      "reason":  str,                 # why we're asking
      "context": { ... },             # tool name, command, paths, ...
      "options": [
         {"id": "allow",   "label": "Allow once",           "default": false},
         {"id": "allow_always", "label": "Allow always in this project"},
         {"id": "deny",    "label": "Deny"},
         ...
      ],
      "preview": {                    # OPTIONAL: diff / output sample
         "type": "diff" | "text" | "table",
         "content": ...
      },
      "suggested": "deny",            # default button
      "id": "appr-xxxxxxxx",          # stable id for the response
      "ts": 1700000000.0,
      "deadline_ts": 1700000060.0     # OPTIONAL: when auto-deny kicks in
    }

The corresponding **response** is:

    {"id": "appr-xxxxxxxx", "choice": "deny", "note": str?}

We persist open approvals to ``.vibecode/runtime/approvals/*.json`` so
a host UI can list pending ones, render them, and reply asynchronously.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

RISK_LEVELS = ("low", "medium", "high", "critical")
KINDS = ("permission", "diff", "elicitation", "notification")

# v0.10 P1 fix: refuse user-supplied IDs that could escape the approvals
# directory via ``..`` / absolute paths / separators.  IDs are generated
# internally as ``appr-<16-hex>`` so this is purely defensive validation
# for the respond / get / wait public API.
_APPR_ID_RX = re.compile(r"^appr-[A-Za-z0-9_-]{4,64}$")


class InvalidApprovalID(ValueError):
    """Raised when a user-supplied appr_id fails the regex guard."""


def _validate_appr_id(appr_id: str) -> None:
    if not isinstance(appr_id, str) or not _APPR_ID_RX.match(appr_id):
        raise InvalidApprovalID(f"invalid appr_id: {appr_id!r} (must match {_APPR_ID_RX.pattern})")


def _approvals_dir(root: Path) -> Path:
    d = root / ".vibecode" / "runtime" / "approvals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _approval_path(root: Path, appr_id: str) -> Path:
    _validate_appr_id(appr_id)
    return _approvals_dir(root) / f"{appr_id}.json"


def _response_path(root: Path, appr_id: str) -> Path:
    _validate_appr_id(appr_id)
    return _approvals_dir(root) / f"{appr_id}.response.json"


def create(
    root: str | os.PathLike,
    *,
    kind: str,
    title: str,
    summary: str,
    risk: str = "medium",
    reason: str = "",
    context: dict[str, Any] | None = None,
    options: list[dict[str, Any]] | None = None,
    preview: dict[str, Any] | None = None,
    suggested: str | None = None,
    deadline_sec: float | None = None,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"unknown approval kind: {kind}; known: {KINDS}")
    if risk not in RISK_LEVELS:
        raise ValueError(f"unknown risk level: {risk}; known: {RISK_LEVELS}")
    root_p = Path(root).resolve()
    appr_id = f"appr-{secrets.token_hex(8)}"
    opts = (
        list(options)
        if options
        else [
            {"id": "allow", "label": "Allow once", "default": False},
            {"id": "deny", "label": "Deny", "default": True},
        ]
    )
    sug = suggested or next((o["id"] for o in opts if o.get("default")), opts[-1]["id"])
    now = time.time()
    payload: dict[str, Any] = {
        "id": appr_id,
        "kind": kind,
        "title": title,
        "summary": summary,
        "risk": risk,
        "reason": reason,
        "context": context or {},
        "options": opts,
        "suggested": sug,
        "ts": now,
    }
    if preview is not None:
        payload["preview"] = preview
    if deadline_sec is not None:
        payload["deadline_ts"] = now + float(deadline_sec)
    # Atomic write via tmp + replace.
    p = _approval_path(root_p, appr_id)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return payload


def list_pending(root: str | os.PathLike) -> list[dict[str, Any]]:
    root_p = Path(root).resolve()
    out: list[dict[str, Any]] = []
    for p in sorted(_approvals_dir(root_p).glob("appr-*.json")):
        if p.name.endswith(".response.json"):
            continue
        rp = p.with_name(p.stem + ".response.json")
        if rp.exists():
            continue
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    # Sort by creation ts asc — oldest first.
    out.sort(key=lambda r: r.get("ts", 0))
    return out


def get(root: str | os.PathLike, appr_id: str) -> dict[str, Any] | None:
    """Return the approval request merged with its response (if any).

    The response, when present, is attached under the ``"response"`` key
    so callers can treat an approval as a single record.  Returns ``None``
    if no approval with that ID exists **or** if the ID fails validation.
    """
    root_p = Path(root).resolve()
    try:
        p = _approval_path(root_p, appr_id)
    except InvalidApprovalID:
        return None
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    rp = _response_path(root_p, appr_id)
    if rp.exists():
        with contextlib.suppress(json.JSONDecodeError):
            data["response"] = json.loads(rp.read_text(encoding="utf-8"))
    return data


def respond(
    root: str | os.PathLike, appr_id: str, *, choice: str, note: str = ""
) -> dict[str, Any]:
    root_p = Path(root).resolve()
    try:
        p = _approval_path(root_p, appr_id)
        rp = _response_path(root_p, appr_id)
    except InvalidApprovalID as e:
        return {"error": str(e)}
    if not p.exists():
        return {"error": f"unknown approval id: {appr_id}"}
    req = json.loads(p.read_text(encoding="utf-8"))
    valid_choices = {o["id"] for o in req.get("options", [])}
    if valid_choices and choice not in valid_choices:
        return {"error": f"choice '{choice}' not in {sorted(valid_choices)}"}
    resp = {"id": appr_id, "choice": choice, "note": note, "ts": time.time()}
    tmp = rp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, rp)
    return resp


def wait(
    root: str | os.PathLike, appr_id: str, *, timeout: float = 300.0, poll_sec: float = 0.2
) -> dict[str, Any]:
    """Block until a response is posted or the deadline / timeout expires.

    Returns the response dict, or auto-denies on timeout / deadline.
    """
    root_p = Path(root).resolve()
    try:
        rp = _response_path(root_p, appr_id)
    except InvalidApprovalID as e:
        return {"error": str(e)}
    req = get(root_p, appr_id) or {}
    deadline = req.get("deadline_ts")
    t0 = time.time()
    while True:
        if rp.exists():
            with contextlib.suppress(json.JSONDecodeError):
                return json.loads(rp.read_text(encoding="utf-8"))
        if time.time() - t0 > timeout:
            return respond(root_p, appr_id, choice="deny", note="timeout")
        if deadline and time.time() > deadline:
            return respond(root_p, appr_id, choice="deny", note="deadline_exceeded")
        time.sleep(poll_sec)


def clear_resolved(root: str | os.PathLike) -> int:
    """Delete approvals that have a matching response.  Returns count."""
    root_p = Path(root).resolve()
    n = 0
    for p in list(_approvals_dir(root_p).glob("appr-*.json")):
        if p.name.endswith(".response.json"):
            continue
        rp = p.with_name(p.stem + ".response.json")
        if rp.exists():
            p.unlink()
            rp.unlink()
            n += 1
    return n
