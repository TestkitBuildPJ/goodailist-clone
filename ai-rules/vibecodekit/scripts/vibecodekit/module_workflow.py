"""Enterprise Module workflow — v5 Pattern F ("thêm module vào codebase có sẵn").

The v5 master spec (``references/30-vibecode-master.md`` Pattern F) covers
the *most common* enterprise scenario: a developer already has a working
codebase and wants to add a new feature module without rebuilding from
scratch.  The workflow is split into two halves:

    REUSE INVENTORY   — what the existing codebase already provides
                        (tech stack, design tokens, auth, ORM, components)
    NEW BUILD         — what new code the module actually needs

The deliverable is a "reuse-max / build-min" plan: every line of new code
must be justified against the inventory, and every existing capability
must be reused unless there's a hard reason not to.

Public API:

* :func:`probe_existing_codebase(root)` — detect Next.js, Prisma, NextAuth,
  Tailwind, Express, FastAPI, Vite, etc. and return a
  :class:`CodebaseProbe`.
* :func:`generate_reuse_inventory(probe)` — derive the canonical reuse
  table from a probe.
* :func:`generate_module_plan(name, spec, probe)` — produce a structured
  module plan (reuse list + new files + acceptance criteria) ready to
  hand off to ``/vibe-blueprint`` and ``/vibe-tip``.

References:
    * ``references/30-vibecode-master.md`` Pattern F (enterprise module).
    * ``references/35-enterprise-module-pattern.md`` (this kit's
      canonical reuse-max-build-min checklist).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


# Ordered detection table: (capability_id, marker_callable, evidence_hint).
# Each detector returns ("evidence string" | None).  We keep this simple
# and explicit so it's easy to extend without changing the probe API.
def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_nextjs(root: Path) -> str | None:
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "next" in deps:
            return f"package.json: next@{deps['next']}"
    if (root / "next.config.js").is_file() or (root / "next.config.ts").is_file():
        return "next.config.* present"
    return None


def _detect_react(root: Path) -> str | None:
    pkg = root / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    if "react" in deps:
        return f"package.json: react@{deps['react']}"
    return None


def _detect_prisma(root: Path) -> str | None:
    if (root / "prisma" / "schema.prisma").is_file():
        return "prisma/schema.prisma"
    pkg = root / "package.json"
    if pkg.is_file():
        text = _read_text(pkg)
        if "@prisma/client" in text:
            return "package.json: @prisma/client"
    return None


def _detect_nextauth(root: Path) -> str | None:
    pkg = root / "package.json"
    if pkg.is_file() and "next-auth" in _read_text(pkg):
        return "package.json: next-auth"
    if (root / "lib" / "auth.ts").is_file() or (root / "auth.ts").is_file():
        return "lib/auth.ts present"
    return None


def _detect_tailwind(root: Path) -> str | None:
    for cand in ("tailwind.config.ts", "tailwind.config.js", "tailwind.config.cjs"):
        if (root / cand).is_file():
            return cand
    pkg = root / "package.json"
    if pkg.is_file() and "tailwindcss" in _read_text(pkg):
        return "package.json: tailwindcss"
    return None


def _detect_express(root: Path) -> str | None:
    pkg = root / "package.json"
    if pkg.is_file() and '"express"' in _read_text(pkg):
        return "package.json: express"
    return None


def _detect_fastapi(root: Path) -> str | None:
    for cand in ("requirements.txt", "pyproject.toml", "Pipfile"):
        path = root / cand
        if path.is_file() and "fastapi" in _read_text(path).lower():
            return f"{cand}: fastapi"
    return None


def _detect_django(root: Path) -> str | None:
    if (root / "manage.py").is_file():
        return "manage.py"
    for cand in ("requirements.txt", "pyproject.toml"):
        path = root / cand
        if path.is_file() and re.search(r"\bdjango\b", _read_text(path).lower()):
            return f"{cand}: django"
    return None


def _detect_vite(root: Path) -> str | None:
    for cand in ("vite.config.ts", "vite.config.js"):
        if (root / cand).is_file():
            return cand
    return None


def _detect_typescript(root: Path) -> str | None:
    if (root / "tsconfig.json").is_file():
        return "tsconfig.json"
    return None


# Order matters — Next.js wins over generic React, Django over generic Python.
_DETECTORS: tuple[tuple[str, Any], ...] = (
    ("nextjs", _detect_nextjs),
    ("react", _detect_react),
    ("vite", _detect_vite),
    ("prisma", _detect_prisma),
    ("nextauth", _detect_nextauth),
    ("tailwind", _detect_tailwind),
    ("express", _detect_express),
    ("fastapi", _detect_fastapi),
    ("django", _detect_django),
    ("typescript", _detect_typescript),
)


@dataclass
class CodebaseProbe:
    """Result of :func:`probe_existing_codebase`."""

    root: str
    is_codebase: bool
    capabilities: dict[str, str] = field(default_factory=dict)
    notable_dirs: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_CODEBASE_MARKERS: tuple[str, ...] = (
    "package.json",
    "pyproject.toml",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
)


def probe_existing_codebase(root: os.PathLike | str) -> CodebaseProbe:
    """Inspect *root* and return what the existing codebase provides.

    A directory is considered a "codebase" if it contains at least one
    canonical project marker (``package.json``, ``pyproject.toml``,
    ``Cargo.toml``, ``go.mod``, ``Gemfile``, ``composer.json``,
    ``pom.xml``, ``build.gradle``).  Empty directories are flagged so
    the workflow can refuse the user gracefully (Pattern F requires an
    *existing* codebase — empty dirs should use ``/vibe-scaffold``).

    The returned :class:`CodebaseProbe` is intentionally tiny — JSON-
    serialisable, no I/O state — so it can be passed across slash-
    command boundaries (e.g. between ``/vibe-module`` and
    ``/vibe-blueprint``).
    """
    root_path = Path(os.fspath(root)).resolve()
    if not root_path.is_dir():
        return CodebaseProbe(str(root_path), False)
    markers = [m for m in _CODEBASE_MARKERS if (root_path / m).is_file()]
    is_codebase = bool(markers)
    capabilities: dict[str, str] = {}
    if is_codebase:
        for cap_id, fn in _DETECTORS:
            evidence = fn(root_path)
            if evidence:
                capabilities[cap_id] = evidence
    notable_dirs = [
        name
        for name in ("app", "components", "lib", "src", "pages", "api", "server", "core", "modules")
        if (root_path / name).is_dir()
    ]
    package_managers: list[str] = []
    if (root_path / "package.json").is_file():
        package_managers.append("npm")
    if (root_path / "pnpm-lock.yaml").is_file():
        package_managers.append("pnpm")
    if (root_path / "yarn.lock").is_file():
        package_managers.append("yarn")
    if (root_path / "pyproject.toml").is_file():
        package_managers.append("pip")
    if (root_path / "Pipfile").is_file():
        package_managers.append("pipenv")
    languages: list[str] = []
    if any((root_path / m).is_file() for m in ("package.json", "tsconfig.json")):
        languages.append("javascript")
    if (root_path / "tsconfig.json").is_file():
        languages.append("typescript")
    if (root_path / "pyproject.toml").is_file() or (root_path / "requirements.txt").is_file():
        languages.append("python")
    if (root_path / "Cargo.toml").is_file():
        languages.append("rust")
    if (root_path / "go.mod").is_file():
        languages.append("go")
    return CodebaseProbe(
        root=str(root_path),
        is_codebase=is_codebase,
        capabilities=capabilities,
        notable_dirs=notable_dirs,
        package_managers=package_managers,
        languages=languages,
    )


# ---------------------------------------------------------------------------
# Reuse inventory
# ---------------------------------------------------------------------------

# Each capability maps to a canonical reuse hint — a one-liner the
# blueprint can drop straight into the "REUSE INVENTORY" table.
_REUSE_HINTS: dict[str, str] = {
    "nextjs": "App Router pages — extend `app/<route>/` with new module pages",
    "react": "Existing component library — reuse design system components",
    "vite": "Vite dev server — register new entry under `src/`",
    "prisma": "Prisma schema + client — extend `schema.prisma` instead of new ORM",
    "nextauth": "NextAuth session — call `getServerSession()` for module gates",
    "tailwind": "Tailwind tokens — reuse `tailwind.config.*` palette/typography",
    "express": "Express router — mount module at `/api/<module>` via `router.use()`",
    "fastapi": "FastAPI app — add `APIRouter` under `api/<module>` with shared deps",
    "django": "Django app — `python manage.py startapp <module>` keeps INSTALLED_APPS",
    "typescript": "Strict TypeScript — reuse existing `tsconfig.json` paths",
}


@dataclass
class ReuseInventoryItem:
    capability: str
    evidence: str
    reuse_hint: str


def generate_reuse_inventory(probe: CodebaseProbe) -> list[ReuseInventoryItem]:
    """Turn a probe's capabilities into a list of canonical reuse items."""
    items: list[ReuseInventoryItem] = []
    for cap_id, evidence in probe.capabilities.items():
        hint = _REUSE_HINTS.get(cap_id, f"reuse existing {cap_id}")
        items.append(
            ReuseInventoryItem(
                capability=cap_id,
                evidence=evidence,
                reuse_hint=hint,
            )
        )
    items.sort(key=lambda x: x.capability)
    return items


# ---------------------------------------------------------------------------
# Module plan
# ---------------------------------------------------------------------------


@dataclass
class ModulePlan:
    name: str
    spec: str
    reuse_inventory: list[ReuseInventoryItem]
    new_files: list[str]
    acceptance_criteria: list[str]
    target_dirs: list[str]
    risks: list[str]
    requires_existing_codebase: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "spec": self.spec,
            "reuse_inventory": [asdict(i) for i in self.reuse_inventory],
            "new_files": list(self.new_files),
            "acceptance_criteria": list(self.acceptance_criteria),
            "target_dirs": list(self.target_dirs),
            "risks": list(self.risks),
            "requires_existing_codebase": self.requires_existing_codebase,
        }


class EmptyCodebaseError(RuntimeError):
    """Raised when Pattern F is invoked on an empty / non-project directory."""


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "module"


def generate_module_plan(
    name: str,
    spec: str,
    probe: CodebaseProbe,
) -> ModulePlan:
    """Compose a reuse-max / build-min plan for *name*.

    Refuses to plan if *probe* shows the target directory is not an
    existing codebase — Pattern F requires reuse, so an empty target
    must go through ``/vibe-scaffold`` first.
    """
    if not probe.is_codebase:
        raise EmptyCodebaseError(
            f"target {probe.root!r} is not an existing codebase "
            f"(no package.json / pyproject.toml / etc.); "
            f"use /vibe-scaffold to bootstrap one first"
        )
    if not name.strip():
        raise ValueError("module name must be non-empty")
    if not spec.strip():
        raise ValueError("module spec must be non-empty")

    inventory = generate_reuse_inventory(probe)
    slug = _slug(name)

    new_files: list[str] = []
    target_dirs: list[str] = []
    risks: list[str] = []

    if "nextjs" in probe.capabilities:
        target_dirs.append(f"app/{slug}")
        new_files.append(f"app/{slug}/page.tsx")
        new_files.append(f"app/{slug}/layout.tsx")
        new_files.append(f"app/api/{slug}/route.ts")
        if "prisma" in probe.capabilities:
            new_files.append(f"prisma/migrations/<ts>_add_{slug}.sql")
            risks.append(
                "Prisma migration must be reviewed; rolling back requires "
                "manual `prisma migrate resolve --rolled-back`."
            )
    elif "fastapi" in probe.capabilities:
        target_dirs.append(f"api/{slug}")
        new_files.append(f"api/{slug}/__init__.py")
        new_files.append(f"api/{slug}/router.py")
        new_files.append(f"api/{slug}/schemas.py")
    elif "express" in probe.capabilities:
        target_dirs.append(f"api/{slug}")
        new_files.append(f"api/{slug}/index.ts")
        new_files.append(f"api/{slug}/routes.ts")
    elif "django" in probe.capabilities:
        target_dirs.append(slug)
        new_files.append(f"{slug}/models.py")
        new_files.append(f"{slug}/views.py")
        new_files.append(f"{slug}/urls.py")
    else:
        # Generic fallback — drop into src/ if it exists.
        base = "src" if "src" in probe.notable_dirs else "."
        target_dirs.append(f"{base}/{slug}")
        new_files.append(f"{base}/{slug}/index.ts")

    if "nextauth" in probe.capabilities:
        risks.append(
            "Module routes must call `getServerSession()` to avoid bypass; "
            "wire auth checks before merging."
        )
    if "tailwind" not in probe.capabilities and any(f.endswith(".tsx") for f in new_files):
        risks.append(
            "No Tailwind detected — module styling must reuse the existing "
            "CSS strategy (CSS modules / styled-components / etc.)."
        )

    acceptance: list[str] = [
        "Module entrypoint is reachable from existing routing",
        f"Reuse inventory ≥ {max(1, len(inventory))} items cited in PR description",
        "Zero duplicate dependencies introduced (diff `package.json` / "
        "`pyproject.toml` shows only additions, never replacements)",
        "All `requires_vision` boundary changes (new auth provider, ORM, "
        "top-level layout) routed through `/vibe-vision` first",
    ]

    return ModulePlan(
        name=name.strip(),
        spec=spec.strip(),
        reuse_inventory=inventory,
        new_files=new_files,
        acceptance_criteria=acceptance,
        target_dirs=target_dirs,
        risks=risks,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vibecodekit module",
        description="Pattern F — enterprise module workflow.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sp_probe = sub.add_parser("probe", help="Probe an existing codebase for reusable capabilities.")
    sp_probe.add_argument(
        "path", nargs="?", default=".", help="Path to existing codebase (default: cwd)."
    )
    sp_plan = sub.add_parser("plan", help="Generate a reuse-max/build-min module plan.")
    sp_plan.add_argument("--name", required=True, help="Module name (becomes URL slug).")
    sp_plan.add_argument("--spec", required=True, help="One-line spec / acceptance description.")
    sp_plan.add_argument(
        "--target", default=".", help="Codebase root to plan against (default: cwd)."
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "probe":
        probe = probe_existing_codebase(args.path)
        print(json.dumps(probe.to_dict(), ensure_ascii=False, indent=2))
        return 0 if probe.is_codebase else 1
    if args.cmd == "plan":
        probe = probe_existing_codebase(args.target)
        try:
            plan = generate_module_plan(args.name, args.spec, probe)
        except EmptyCodebaseError as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
            return 2
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
