"""Runtime doctor — validates a vibecode project layout.

Graceful: when asked to run against a *skill bundle* (no ``.claw.json``, no
``CLAUDE.md``, no ``ai-rules``) it reports which optional files are missing
without failing the whole check.  This fixes the v0.6 regression where
``runtime_doctor_v06`` mis-classified skill bundles as broken projects.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REQUIRED_FILES: list[str] = []  # v0.7 has no hard-required files
ADVISORY_FILES: list[str] = [
    ".claw.json",
    "CLAUDE.md",
    ".claude/commands",
    ".claude/agents",
    "ai-rules/vibecodekit",
    ".claw/hooks",
]

# HOTFIX-002: runtime assets that MUST land under ai-rules/vibecodekit/ for
# load_rri_questions(), ScaffoldEngine, conformance probes, and methodology
# rendering to work.  Paths are relative to ai-rules/vibecodekit/.
REQUIRED_RUNTIME_ASSETS: list[str] = [
    "assets/rri-question-bank.json",
    "assets/scaffolds/docs/manifest.json",
    "assets/scaffolds/saas/manifest.json",
    "assets/scaffolds/portfolio/manifest.json",
    "assets/templates/vision.md",
    "assets/templates/rri-matrix.md",
    "references/34-style-tokens.md",
    "references/36-copy-patterns.md",
]


def _is_skill_repo(root: Path) -> bool:
    """Detect the skill bundle's source layout (overlay lives under
    ``update-package/`` instead of the project root).

    A skill repo has ``update-package/CLAUDE.md`` + ``update-package/.claw.json``
    + ``scripts/vibecodekit/`` at the root; advisory files like ``CLAUDE.md``
    and ``.claude/commands`` are *expected* to be missing because they are
    shipped under ``update-package/`` for installation into downstream
    projects (audit v0.16.0 finding E).
    """
    return (
        (root / "update-package" / "CLAUDE.md").is_file()
        and (root / "update-package" / ".claw.json").is_file()
        and (root / "scripts" / "vibecodekit").is_dir()
    )


def check(root: str | os.PathLike = ".", installed_only: bool = False) -> dict:
    root = Path(root).resolve()
    ok: list[str] = []
    missing: list[str] = []
    skill_repo = _is_skill_repo(root)
    for rel in ADVISORY_FILES:
        # When invoked from inside the skill repo, advisory files live
        # under ``update-package/`` rather than the project root — count
        # that as "present" so doctor doesn't yell at maintainers running
        # from the source tree.
        if (root / rel).exists() or skill_repo and (root / "update-package" / rel).exists():
            ok.append(rel)
        else:
            missing.append(rel)
    runtime = root / ".vibecode" / "runtime"
    runtime_exists = runtime.exists()
    # Try importing the package to catch path issues.
    try:
        import vibecodekit  # type: ignore  # noqa: F401

        pkg_ok = True
        pkg_error = ""
    except Exception as e:
        pkg_ok = False
        pkg_error = f"{type(e).__name__}: {e}"

    # Detect the "placeholder" state: update package extracted but the
    # reconciliation installer hasn't been run yet.  When ai-rules/vibecodekit
    # exists but contains no runtime scripts, warn loudly so the user knows
    # the overlay isn't actually wired up — even though `package_importable`
    # may be True because vibecodekit was imported from a *different* path
    # (e.g. the skill bundle's scripts dir via PYTHONPATH).
    warnings: list[str] = []
    runtime_dir = root / "ai-rules" / "vibecodekit"
    runtime_scripts = runtime_dir / "scripts" / "vibecodekit" / "cli.py"
    runtime_placeholder = runtime_dir.exists() and not runtime_scripts.is_file()
    if runtime_placeholder:
        warnings.append(
            "ai-rules/vibecodekit/ is a placeholder — run the reconciliation "
            "installer (python -m vibecodekit.cli install <project>) from the "
            "skill bundle to copy scripts/references/templates into this "
            "directory. `package_importable` may still be True if vibecodekit "
            "was loaded from another PYTHONPATH."
        )
    if pkg_ok and not runtime_scripts.is_file() and not runtime_exists:
        warnings.append(
            "vibecodekit is importable but no project-local runtime found "
            "at ai-rules/vibecodekit/scripts/ or .vibecode/runtime/."
        )

    # HOTFIX-002: verify required runtime assets are present under the
    # installed ai-rules/vibecodekit/ tree.  When the tree exists but an asset
    # is missing, that means the installer either didn't run or shipped an
    # incomplete set — both are release-blocking for installed projects.
    runtime_assets_missing: list[str] = []
    if runtime_dir.exists() and not runtime_placeholder:
        for rel in REQUIRED_RUNTIME_ASSETS:
            if not (runtime_dir / rel).exists():
                runtime_assets_missing.append(rel)
        if runtime_assets_missing:
            warnings.append(
                "missing required runtime assets under ai-rules/vibecodekit/: "
                + ", ".join(runtime_assets_missing)
                + ". Re-run `python -m vibecodekit.cli install <project>` "
                "from an up-to-date skill bundle."
            )

    exit_code = 0
    if installed_only:
        # In installed-only mode, placeholder runtime counts as a failure
        # — user asked us to verify installation, not just loose imports.
        if missing or runtime_placeholder or runtime_assets_missing:
            exit_code = 1
    return {
        "root": str(root),
        "skill_repo": skill_repo,
        "advisory_present": ok,
        "advisory_missing": missing,
        "runtime_exists": runtime_exists,
        "runtime_placeholder": runtime_placeholder,
        "runtime_assets_missing": runtime_assets_missing,
        "package_importable": pkg_ok,
        "package_error": pkg_error,
        "warnings": warnings,
        "exit_code": exit_code,
        "installed_only": installed_only,
    }


def _main() -> None:
    ap = argparse.ArgumentParser(description="Check vibecode project health.")
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--installed-only",
        action="store_true",
        help="Non-zero exit code if any advisory file is missing (use only when the project claims to be fully installed).",
    )
    args = ap.parse_args()
    out = check(args.root, installed_only=args.installed_only)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(out["exit_code"])


if __name__ == "__main__":
    _main()
