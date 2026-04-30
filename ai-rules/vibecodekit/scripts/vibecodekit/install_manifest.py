"""Reconciliation-based install (Pattern #16).

Treats the destination project as the *desired state*.  For every tracked
source → destination pair we compute the diff:

    PRESENT  source matches destination  (content hash equal)       → skip
    OUTDATED source and destination differ                          → overwrite
    MISSING  source exists, destination doesn't                     → create
    ORPHAN   destination exists but source doesn't                  → left alone (no deletes)

By default we never delete files already in the destination.  Users who want
a clean install should remove ``ai-rules/vibecodekit`` themselves.

References:
- ``references/16-reconciliation-install.md``
- ``references/27-mcp-adapter.md``
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl as _fcntl  # POSIX only
except ImportError:  # pragma: no cover — Windows fallback.
    _fcntl = None  # type: ignore[assignment]


PACKAGE_ROOT = Path(__file__).resolve().parent  # .../scripts/vibecodekit
SKILL_ROOT = PACKAGE_ROOT.parent.parent  # .../skill/vibecodekit-hybrid-ultra


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Planned:
    source: str
    destination: str
    action: str  # "skip" | "create" | "overwrite"


def plan(dst_root: str | os.PathLike) -> list[Planned]:
    dst = Path(dst_root).resolve()
    out: list[Planned] = []
    # All runtime scripts go to ai-rules/vibecodekit/scripts/vibecodekit/
    src_scripts = SKILL_ROOT / "scripts"
    for p in sorted(src_scripts.rglob("*.py")):
        rel = p.relative_to(src_scripts)
        d = dst / "ai-rules" / "vibecodekit" / "scripts" / rel
        action = (
            "skip"
            if d.exists() and _sha(p) == _sha(d)
            else ("overwrite" if d.exists() else "create")
        )
        out.append(Planned(str(p), str(d), action))
    # Reference markdown → ai-rules/vibecodekit/references/
    src_refs = SKILL_ROOT / "references"
    if src_refs.exists():
        for p in sorted(src_refs.rglob("*.md")):
            rel = p.relative_to(src_refs)
            d = dst / "ai-rules" / "vibecodekit" / "references" / rel
            action = (
                "skip"
                if d.exists() and _sha(p) == _sha(d)
                else ("overwrite" if d.exists() else "create")
            )
            out.append(Planned(str(p), str(d), action))
    # Templates — preserve the ``assets/`` prefix so the runtime paths resolved
    # by probes and methodology (``parents[2] / "assets" / "templates"``) are
    # valid on the installed project.  We also keep a sibling copy at
    # ``ai-rules/vibecodekit/templates/`` for backwards compatibility with
    # user-visible doc paths from v0.11.2.
    src_tpl = SKILL_ROOT / "assets" / "templates"
    if src_tpl.exists():
        for p in sorted(src_tpl.rglob("*")):
            if p.is_file():
                rel = p.relative_to(SKILL_ROOT)  # e.g. assets/templates/vision.md
                d = dst / "ai-rules" / "vibecodekit" / rel
                action = (
                    "skip"
                    if d.exists() and _sha(p) == _sha(d)
                    else ("overwrite" if d.exists() else "create")
                )
                out.append(Planned(str(p), str(d), action))
                # Backwards-compat mirror under templates/ (legacy v0.11.2 path).
                rel_legacy = p.relative_to(src_tpl)
                d_legacy = dst / "ai-rules" / "vibecodekit" / "templates" / rel_legacy
                action_legacy = (
                    "skip"
                    if d_legacy.exists() and _sha(p) == _sha(d_legacy)
                    else ("overwrite" if d_legacy.exists() else "create")
                )
                out.append(Planned(str(p), str(d_legacy), action_legacy))
    # SKILL.md itself goes to ai-rules/vibecodekit/
    src_skill = SKILL_ROOT / "SKILL.md"
    if src_skill.exists():
        d = dst / "ai-rules" / "vibecodekit" / "SKILL.md"
        action = (
            "skip"
            if d.exists() and _sha(src_skill) == _sha(d)
            else ("overwrite" if d.exists() else "create")
        )
        out.append(Planned(str(src_skill), str(d), action))
    # Plugin manifest + sample runtime payloads + top-level metadata ship
    # alongside the skill.  ``manifest.llm.json`` is consumed by host LLMs,
    # ``VERSION`` is read by ``vibecodekit.__version__``, ``CHANGELOG.md`` is
    # referenced from docs links, so all three must land in the installed tree.
    for asset_rel in (
        "assets/plugin-manifest.json",
        "runtime/sample-plan.json",
        "manifest.llm.json",
        "VERSION",
        "CHANGELOG.md",
    ):
        src_asset = SKILL_ROOT / asset_rel
        if src_asset.exists():
            d = dst / "ai-rules" / "vibecodekit" / asset_rel
            action = (
                "skip"
                if d.exists() and _sha(src_asset) == _sha(d)
                else ("overwrite" if d.exists() else "create")
            )
            out.append(Planned(str(src_asset), str(d), action))
    # v0.11.2 (FIX-006): runtime data assets that ``methodology`` and
    # ``scaffold_engine`` resolve relative to ``parents[2]/assets/`` MUST be
    # shipped to the installed location, otherwise ``load_rri_questions()`` and
    # ``scaffold_engine.list_presets()`` fail in deployed projects.
    src_assets = SKILL_ROOT / "assets"
    if src_assets.exists():
        # Top-level JSON data (rri-question-bank.json + future siblings).
        for p in sorted(src_assets.glob("*.json")):
            rel = p.relative_to(SKILL_ROOT)
            d = dst / "ai-rules" / "vibecodekit" / rel
            action = (
                "skip"
                if d.exists() and _sha(p) == _sha(d)
                else ("overwrite" if d.exists() else "create")
            )
            out.append(Planned(str(p), str(d), action))
        # Scaffold presets (Pattern A/B/C/D + portfolio/saas/landing/…).
        scaffolds = src_assets / "scaffolds"
        if scaffolds.exists():
            for p in sorted(scaffolds.rglob("*")):
                if p.is_file():
                    rel = p.relative_to(SKILL_ROOT)
                    d = dst / "ai-rules" / "vibecodekit" / rel
                    action = (
                        "skip"
                        if d.exists() and _sha(p) == _sha(d)
                        else ("overwrite" if d.exists() else "create")
                    )
                    out.append(Planned(str(p), str(d), action))
    return out


@contextlib.contextmanager
def _install_lock(dst: Path) -> Iterator[None]:
    """v0.11.4 P3-1: advisory fcntl lock scoped to ``dst``.

    Ensures that two concurrent ``install()`` calls against the same
    destination serialise at the plan-and-apply boundary.  The second
    caller blocks until the first finishes, at which point re-planning
    sees all files already present and reports them as ``skip`` — the
    intended idempotent outcome.

    On non-POSIX platforms (``fcntl`` missing) the lock is a no-op so
    Windows installers still work; atomicity there is best-effort.
    """
    lock_dir = dst / ".vibecode" / "runtime"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "install.lock"
    # ``open`` with ``a+`` so the file exists for flock but contents are
    # preserved across callers (useful for debugging who held the lock).
    with open(lock_path, "a+", encoding="utf-8") as fh:
        if _fcntl is not None:
            _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)
        try:
            yield
        finally:
            if _fcntl is not None:
                _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)


def install(dst_root: str | os.PathLike, *, dry_run: bool = False) -> dict:
    dst = Path(dst_root).resolve()
    # v0.11.4 P3-1: serialise concurrent installers on the same dst so
    # re-planning always sees a committed filesystem view, not one mid-
    # write by another process.  The lock is only taken for the real
    # copy step — ``dry_run`` skips acquisition to avoid creating a
    # lock-file side effect when the user only wanted to preview.
    if dry_run:
        pl = plan(dst_root)
    else:
        dst.mkdir(parents=True, exist_ok=True)
        with _install_lock(dst):
            pl = plan(dst_root)
            for p in pl:
                if p.action == "skip":
                    continue
                s, d = Path(p.source), Path(p.destination)
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)
    skipped = sum(1 for p in pl if p.action == "skip")
    planned_copies = sum(1 for p in pl if p.action == "overwrite")
    planned_creates = sum(1 for p in pl if p.action == "create")
    return {
        "dry_run": dry_run,
        "total": len(pl),
        "skipped": skipped,
        "planned_copies": planned_copies,
        "planned_creates": planned_creates,
        "operations": [
            {"source": p.source, "destination": p.destination, "action": p.action} for p in pl
        ],
    }


def _main() -> None:
    ap = argparse.ArgumentParser(description="Reconciliation-based install into a target project.")
    ap.add_argument("destination")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = install(args.destination, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"dry_run: {out['dry_run']}")
        print(
            f"total: {out['total']}  skip: {out['skipped']}  overwrite: {out['planned_copies']}  create: {out['planned_creates']}"
        )


if __name__ == "__main__":
    _main()
