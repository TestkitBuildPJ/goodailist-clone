"""Parse tool-use blocks from a free-form text prompt (Pattern #2 supporting code).

Accepts two notations:

    1. Claude-Code-like JSON array::

         [
           {"tool": "read_file", "input": {"path": "README.md"}},
           {"tool": "grep",       "input": {"pattern": "TODO"}}
         ]

    2. Inline fences::

         <tool name="read_file">{"path":"README.md"}</tool>
         <tool name="grep">{"pattern":"TODO"}</tool>

Returns a list of dicts (possibly empty).  Malformed blocks are skipped
rather than raising — the query loop should keep going.
"""

from __future__ import annotations

import json
import re

_TAG_RX = re.compile(r"<tool\s+name=\"([a-z_]+)\">\s*(\{.*?\})\s*</tool>", re.DOTALL)


def parse_tool_uses(text: str) -> list[dict]:
    if not text or not text.strip():
        return []

    blocks: list[dict] = []
    # Try raw JSON array first.
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and entry.get("tool"):
                blocks.append({"tool": entry["tool"], "input": entry.get("input") or {}})
        if blocks:
            return blocks

    # Fall back to <tool> tags.
    for m in _TAG_RX.finditer(text):
        name = m.group(1)
        try:
            inp = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        blocks.append({"tool": name, "input": inp})
    return blocks
