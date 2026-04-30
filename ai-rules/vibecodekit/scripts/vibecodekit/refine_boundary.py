"""REFINE boundary classifier — step 8 of the v5 8-step VIBECODE pipeline.

The v5 master prompt (`references/30-vibecode-master.md` §8) defines what
a *legal* refine looks like:

    CÓ THỂ REFINE (in-scope for `/vibe-refine`):
      • Thay đổi text / copy
      • Điều chỉnh màu nhỏ (CSS tokens)
      • Thêm/bớt nội dung trong section có sẵn
      • Fix issues từ Verify Report

    KHÔNG THỂ (cần quay BƯỚC 3 — VISION):
      • Thêm section / feature / route / component mới
      • Đổi layout / structure
      • Thay đổi tech stack / dependencies
      • Thêm module / migration / schema mới

This module turns that prose into a deterministic classifier so the
runtime can refuse refines that are actually structural changes in
disguise.

Inputs: a unified diff (string) OR a list of per-file change descriptors:

    {"path": "...", "status": "added"|"modified"|"deleted"|"renamed",
     "added_lines": [...], "removed_lines": [...]}

Output: ``{"kind": "in_scope"|"requires_vision",
           "reasons": [...],            # always present
           "signals": {...}}``          # detailed evidence

References:
    * ``references/30-vibecode-master.md`` §8 (REFINE limits)
    * ``references/29-rri-reverse-interview.md`` (vision step that owns
      structural changes)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any

# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

# Files whose mere addition implies a structural change.  Editing them is
# usually fine; *creating* one is not.
_NEW_FILE_REQUIRES_VISION = (
    re.compile(r"(^|/)app/[^/]+/page\.[tj]sx?$"),
    re.compile(r"(^|/)pages/[^/]+\.[tj]sx?$"),
    re.compile(r"(^|/)app/api/[^/]+/route\.[tj]sx?$"),
    re.compile(r"(^|/)pages/api/[^/]+\.[tj]sx?$"),
    re.compile(r"(^|/)src/components/[^/]+\.[tj]sx?$"),
    re.compile(r"(^|/)components/[^/]+\.[tj]sx?$"),
    re.compile(r"(^|/)src/lib/[^/]+\.[tj]sx?$"),
    re.compile(r"(^|/)prisma/migrations/"),
    re.compile(r"(^|/)alembic/versions/"),
    re.compile(r"(^|/)migrations/[^/]+\.(sql|py|ts)$"),
)

# Files that, when *modified*, almost always indicate a structural change.
_MODIFY_REQUIRES_VISION = (
    re.compile(r"(^|/)package\.json$"),
    re.compile(r"(^|/)package-lock\.json$"),
    re.compile(r"(^|/)yarn\.lock$"),
    re.compile(r"(^|/)pnpm-lock\.yaml$"),
    re.compile(r"(^|/)requirements\.txt$"),
    re.compile(r"(^|/)pyproject\.toml$"),
    re.compile(r"(^|/)poetry\.lock$"),
    re.compile(r"(^|/)Cargo\.toml$"),
    re.compile(r"(^|/)Cargo\.lock$"),
    re.compile(r"(^|/)go\.mod$"),
    re.compile(r"(^|/)go\.sum$"),
    re.compile(r"(^|/)prisma/schema\.prisma$"),
    re.compile(r"(^|/)next\.config\.[jt]s$"),
    re.compile(r"(^|/)tsconfig\.json$"),
    re.compile(r"(^|/)tailwind\.config\.[jt]s$"),
    re.compile(r"(^|/)Dockerfile$"),
    re.compile(r"(^|/)docker-compose\.ya?ml$"),
    re.compile(r"(^|/)\.github/workflows/"),
)

# Files where additions/removals are pure copy — always in_scope.
_PURE_TEXT = (
    re.compile(r"(^|/)README(\.md)?$", re.IGNORECASE),
    re.compile(r"(^|/)CHANGELOG(\.md)?$", re.IGNORECASE),
    re.compile(r"(^|/)docs/.+\.(md|mdx)$"),
    re.compile(r"\.md$"),
    re.compile(r"\.mdx$"),
    re.compile(r"(^|/)public/.+\.(svg|png|jpg|jpeg|webp|ico)$"),
)

# CSS/SCSS files: token-only edits stay in_scope.
_CSS_FILE = re.compile(r"\.(css|scss|sass)$")

# Patterns inside diff lines that smell structural.
_STRUCTURAL_LINE_PATTERNS = (
    # New route export in a Next.js page/route file.
    re.compile(r"^\s*export\s+(default\s+)?(async\s+)?function\b"),
    re.compile(r"^\s*export\s+const\s+\w+\s*="),
    # Schema / migration changes (raw SQL or Prisma model declarations).
    re.compile(r"^\s*model\s+[A-Z]\w+\s*\{"),
    re.compile(r"^\s*CREATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"^\s*ALTER\s+TABLE\b", re.IGNORECASE),
    re.compile(r"^\s*DROP\s+TABLE\b", re.IGNORECASE),
    # New top-level React component (capitalised JSX-returning function).
    re.compile(r"^\s*function\s+[A-Z]\w+\s*\("),
    re.compile(r"^\s*const\s+[A-Z]\w+\s*=\s*\("),
)


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

_DIFF_HEADER = re.compile(r"^diff --git a/(.+?) b/(.+?)$")
_NEW_FILE_LINE = re.compile(r"^new file mode\b")
_DELETED_FILE_LINE = re.compile(r"^deleted file mode\b")
_RENAME_FROM = re.compile(r"^rename from (.+)$")
_RENAME_TO = re.compile(r"^rename to (.+)$")


def _parse_unified_diff(text: str) -> list[dict[str, Any]]:
    """Best-effort unified-diff parser tailored to ``git diff`` output."""
    files: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    lines = text.splitlines()
    for raw in lines:
        m = _DIFF_HEADER.match(raw)
        if m:
            if cur is not None:
                files.append(cur)
            cur = {
                "path": m.group(2),
                "status": "modified",
                "added_lines": [],
                "removed_lines": [],
            }
            continue
        if cur is None:
            continue
        if _NEW_FILE_LINE.match(raw):
            cur["status"] = "added"
        elif _DELETED_FILE_LINE.match(raw):
            cur["status"] = "deleted"
        elif _RENAME_TO.match(raw):
            cur["status"] = "renamed"
            cur["path"] = _RENAME_TO.match(raw).group(1)
        elif raw.startswith("+++ ") or raw.startswith("--- "):
            continue
        elif raw.startswith("+") and not raw.startswith("+++"):
            cur["added_lines"].append(raw[1:])
        elif raw.startswith("-") and not raw.startswith("---"):
            cur["removed_lines"].append(raw[1:])
    if cur is not None:
        files.append(cur)
    return files


def _normalize_path(path: str) -> str:
    return str(PurePosixPath(path))


def _matches_any(path: str, patterns: Sequence[re.Pattern]) -> bool:
    p = _normalize_path(path)
    return any(pat.search(p) for pat in patterns)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_change(
    change: Any,
    *,
    max_files: int = 50,
) -> dict[str, Any]:
    """Classify a refine candidate as ``in_scope`` or ``requires_vision``.

    ``change`` can be:
      * A unified-diff string (``git diff`` output).
      * A list of file descriptors (see module docstring).
      * A dict with key ``files`` containing such a list.

    Returns ``{"kind": ..., "reasons": [...], "signals": {...}}``.
    """
    if isinstance(change, str):
        files = _parse_unified_diff(change)
    elif isinstance(change, dict) and "files" in change:
        files = list(change["files"])
    elif isinstance(change, (list, tuple)):
        files = list(change)
    else:
        raise TypeError(
            "change must be a unified-diff string, a list of file dicts, "
            "or a dict with a 'files' key."
        )

    reasons: list[str] = []
    signals: dict[str, Any] = {
        "files_total": len(files),
        "files_added": 0,
        "files_deleted": 0,
        "files_renamed": 0,
        "structural_files": [],
        "structural_lines": [],
    }

    if len(files) > max_files:
        signals["truncated"] = True
        files = files[:max_files]

    for entry in files:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path", ""))
        status = (entry.get("status") or "modified").lower()
        added = entry.get("added_lines") or []

        if status == "added":
            signals["files_added"] += 1
            if _matches_any(path, _NEW_FILE_REQUIRES_VISION):
                reasons.append(
                    f"new structural file: {path} — adding routes / pages "
                    f"/ components / migrations is a Vision change"
                )
                signals["structural_files"].append({"path": path, "reason": "new_structural_file"})
                continue
            # Pure-text new files (md/mdx/svg) stay in_scope.
            if not _matches_any(path, _PURE_TEXT):
                reasons.append(
                    f"new non-text file: {path} — adding new code files " f"is typically structural"
                )
                signals["structural_files"].append({"path": path, "reason": "new_non_text_file"})
                continue

        if status == "deleted":
            signals["files_deleted"] += 1
            if not _matches_any(path, _PURE_TEXT):
                reasons.append(
                    f"file deletion: {path} — removing files is typically " f"structural"
                )
                signals["structural_files"].append({"path": path, "reason": "file_deletion"})
                continue

        if status == "renamed":
            signals["files_renamed"] += 1
            reasons.append(f"file rename: {path} — restructure")
            signals["structural_files"].append({"path": path, "reason": "file_rename"})
            continue

        if _matches_any(path, _MODIFY_REQUIRES_VISION):
            reasons.append(
                f"sensitive file modified: {path} — config / lockfile / "
                f"schema changes need Vision review"
            )
            signals["structural_files"].append({"path": path, "reason": "sensitive_modify"})
            continue

        # Inspect added lines for structural patterns.
        if not _matches_any(path, _PURE_TEXT) and not _CSS_FILE.search(_normalize_path(path)):
            for line in added:
                for pat in _STRUCTURAL_LINE_PATTERNS:
                    if pat.search(line):
                        snippet = line.strip()[:120]
                        reasons.append(f"structural line in {path}: '{snippet}'")
                        signals["structural_lines"].append({"path": path, "line": snippet})
                        break
                else:
                    continue
                break

    if reasons:
        kind = "requires_vision"
    else:
        kind = "in_scope"
    return {"kind": kind, "reasons": reasons, "signals": signals}


# ---------------------------------------------------------------------------
# CLI entry-point (used by `vibecodekit refine classify`)
# ---------------------------------------------------------------------------


def cli_classify(args: argparse.Namespace) -> int:
    if args.input == "-":
        text = sys.stdin.read()
    elif os.path.isfile(args.input):
        with open(args.input, encoding="utf-8") as fh:
            text = fh.read()
    else:
        # Treat as literal diff content.
        text = args.input

    result = classify_change(text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Exit code 0 if in-scope, 1 if requires-vision (so CI / hooks can gate).
    return 0 if result["kind"] == "in_scope" else 1


def _main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="refine_boundary",
        description="Classify a refine candidate (in_scope vs requires_vision).",
    )
    sp = ap.add_subparsers(dest="cmd", required=True)
    classify = sp.add_parser(
        "classify",
        help="Read a unified diff (file path, '-' for stdin, "
        "or literal text) and emit JSON verdict.",
    )
    classify.add_argument("input")
    classify.set_defaults(fn=cli_classify)
    args = ap.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    sys.exit(_main())
