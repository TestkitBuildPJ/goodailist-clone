"""Skill discovery (Patterns #11 + #13).

Walk the project tree for ``.claude/skills/*/SKILL.md`` and optionally filter
by a touched file path (conditional activation).  Gitignored directories and
``node_modules`` are excluded (prevents supply-chain injection —
Giải phẫu §9.4.2).

References:
- ``references/11-conditional-skill-activation.md``
- ``references/13-dynamic-skill-discovery.md``
- ``references/20-lifecycle.md``
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
from pathlib import Path
from typing import Any

_IGNORED_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    ".vibecode",
    ".venv",
    "venv",
    "__pycache__",
}
_FRONT_RX = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    m = _FRONT_RX.search(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, Any] = {}
    key = None
    for line in block.splitlines():
        if line.startswith("  - "):
            if isinstance(out.get(key), list):
                out[key].append(line[4:].strip().strip('"').strip("'"))
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if v == "":
                out[k] = []
                key = k
            elif v.startswith("[") and v.endswith("]"):
                out[k] = [s.strip().strip('"').strip("'") for s in v[1:-1].split(",") if s.strip()]
                key = k
            else:
                out[k] = v.strip('"').strip("'")
                key = k
    return out


def discover(root: str | os.PathLike, touched: str | None = None) -> list[dict[str, Any]]:
    root = Path(root).resolve()
    found: list[dict[str, Any]] = []
    for base in root.rglob("SKILL.md"):
        parts = set(base.parts)
        if parts & _IGNORED_DIRS:
            continue
        text = base.read_text(encoding="utf-8", errors="ignore")
        fm = _parse_frontmatter(text)
        paths = fm.get("paths") or []
        if touched and paths:
            if not any(fnmatch.fnmatchcase(touched, p) for p in paths):
                continue
        found.append(
            {
                "name": fm.get("name") or base.parent.name,
                "version": fm.get("version"),
                "description": fm.get("description", ""),
                "path": str(base.relative_to(root)),
                "paths": paths,
            }
        )
    return found


def _main() -> None:
    ap = argparse.ArgumentParser(description="Discover skills under a project root.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--touched", default=None)
    args = ap.parse_args()
    print(json.dumps(discover(args.root, args.touched), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()


# ---------------------------------------------------------------------------
# v0.11.3 / Patch C — Path-based activation API
# ---------------------------------------------------------------------------


def _self_skill_md() -> Path | None:
    """Locate the kit's own ``SKILL.md`` across known layouts."""
    env = os.environ.get("VIBECODE_SKILL_ROOT")
    if env:
        cand = Path(env) / "SKILL.md"
        if cand.exists():
            return cand
    here = Path(__file__).resolve()
    # scripts/vibecodekit/<file>.py → parents[2] = skill bundle root
    skill_root = here.parents[2]
    cand = skill_root / "SKILL.md"
    if cand.exists():
        return cand
    return None


def _match_glob(pattern: str, path: str) -> bool:
    """Glob match that treats ``**`` as "zero or more directories".

    Plain :func:`fnmatch.fnmatchcase` treats ``**`` as a literal ``*``
    repeated which fails to match top-level files against globs like
    ``**/*.py``.  We expand the pattern: every leading ``**/`` segment
    is tried both **with** and **without** that prefix, so
    ``**/*.py`` matches both ``foo.py`` and ``src/foo.py``.
    """
    norm = path.replace("\\", "/")
    candidates = {pattern}
    cur = pattern
    while cur.startswith("**/"):
        cur = cur[3:]
        candidates.add(cur)
    return any(fnmatch.fnmatchcase(norm, c) for c in candidates)


def activate_for(touched: str) -> dict[str, Any]:
    """Decide whether the v0.11.x skill activates for a touched file.

    Returns a dict with:
      ``activate``  — bool (True iff at least one ``paths:`` glob matched)
      ``skill``     — the skill name from frontmatter
      ``matched``   — list of glob patterns that matched
      ``reason``    — short machine-readable code
    """
    skill_md = _self_skill_md()
    if skill_md is None:
        return {"activate": False, "skill": None, "matched": [], "reason": "skill_md_missing"}
    text = skill_md.read_text(encoding="utf-8", errors="ignore")
    fm = _parse_frontmatter(text)
    paths = fm.get("paths") or []
    name = fm.get("name") or skill_md.parent.name
    if not paths:
        return {"activate": False, "skill": name, "matched": [], "reason": "no_paths_declared"}
    if not touched:
        return {"activate": False, "skill": name, "matched": [], "reason": "empty_touched"}
    matched = [p for p in paths if _match_glob(p, touched)]
    if matched:
        return {"activate": True, "skill": name, "matched": matched, "reason": "path_match"}
    return {"activate": False, "skill": name, "matched": [], "reason": "no_match"}
