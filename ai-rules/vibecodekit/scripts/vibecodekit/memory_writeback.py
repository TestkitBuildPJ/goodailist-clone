"""CLAUDE.md auto-maintain (v0.11.0, Phase β — F6).

Inspired by taw-kit's ``taw memory init/update/check/nest``, extended for
VibecodeKit:

- **5 auto-maintained sections** (taw has 3): ``stack``, ``scripts``,
  ``conventions``, ``gotchas`` (mined from ``.vibecode/run-history``),
  ``test-strategy``.
- **Marker-strict mode**: only content between
  ``<!-- vibecode:auto:<section>:begin -->`` …
  ``<!-- vibecode:auto:<section>:end -->`` is ever overwritten.
  User content outside markers is preserved byte-for-byte.
- **Drift detection** (``check()``): compares current auto-section
  bodies against a *fresh* render and reports differences.
- **Nested CLAUDE.md** support: ``nest()`` creates a per-subdirectory
  ``CLAUDE.md`` with the same marker convention.
- **Dry-run + diff preview**: every operation can be inspected before
  it lands on disk.

Public API::

    from vibecodekit.memory_writeback import MemoryWriteback
    mw = MemoryWriteback(repo_dir=Path("."))
    diff = mw.update()              # refresh auto sections
    drift = mw.check()              # report stale sections
    nested = mw.nest("apps/api")    # create nested file

Section sources (best-effort detection — never fail):

- **stack**     :  ``package.json`` engines, ``pyproject.toml``,
                   ``requirements.txt``, ``go.mod``, etc.
- **scripts**   :  ``package.json`` scripts, ``Makefile`` targets,
                   ``pyproject.toml`` `[tool.poetry.scripts]`.
- **conventions**: detected file-organisation patterns (``src/api``
                   for FastAPI, ``app/`` for Next.js, ``components/``).
- **gotchas**   :  recurrent error patterns from
                   ``.vibecode/run-history.jsonl`` if present.
- **test-strategy**: detected test framework (`pytest` / `vitest` /
                     `jest`) + how to run.

References:
- ``references/24-memory-governance.md``
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

_MARKER_BEGIN = "<!-- vibecode:auto:{name}:begin -->"
_MARKER_END = "<!-- vibecode:auto:{name}:end -->"
_MARKER_RE = re.compile(
    r"<!--\s*vibecode:auto:(?P<name>[a-z0-9\-]+):begin\s*-->\n?"
    r"(?P<body>.*?)"
    r"<!--\s*vibecode:auto:(?P=name):end\s*-->",
    flags=re.DOTALL,
)

_SECTIONS = ("stack", "scripts", "conventions", "gotchas", "test-strategy")


@dataclasses.dataclass(frozen=True)
class DiffReport:
    path: Path
    sections_added: tuple[str, ...]
    sections_updated: tuple[str, ...]
    sections_removed: tuple[str, ...]
    bytes_before: int
    bytes_after: int
    preview: str  # unified-diff style, truncated

    @property
    def changed(self) -> bool:
        return bool(self.sections_added or self.sections_updated or self.sections_removed)


@dataclasses.dataclass(frozen=True)
class DriftReport:
    path: Path
    drifted: tuple[str, ...]
    missing: tuple[str, ...]
    extra: tuple[str, ...]  # auto-section names found that we don't manage

    @property
    def in_sync(self) -> bool:
        return not (self.drifted or self.missing)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _detect_stack(repo: Path) -> str:
    bits: list[str] = []
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(_read(pkg))
        except json.JSONDecodeError:
            data = {}
        engines = data.get("engines", {}) or {}
        deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
        if "next" in deps:
            bits.append(f"- **Next.js** {deps['next']}")
        if "react" in deps:
            bits.append(f"- **React** {deps['react']}")
        if "expo" in deps:
            bits.append(f"- **Expo** {deps['expo']}")
        if "node" in engines:
            bits.append(f"- **Node** {engines['node']}")
    py = repo / "pyproject.toml"
    if py.is_file():
        text = _read(py)
        m = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
        if m:
            bits.append(f"- **Python** {m.group(1)}")
        if "fastapi" in text.lower():
            bits.append("- **FastAPI** detected")
        if "django" in text.lower():
            bits.append("- **Django** detected")
    if (repo / "go.mod").is_file():
        m = re.search(r"^go\s+(\S+)", _read(repo / "go.mod"), re.MULTILINE)
        if m:
            bits.append(f"- **Go** {m.group(1)}")
    if (repo / "Cargo.toml").is_file():
        bits.append("- **Rust** (Cargo)")
    return "\n".join(bits) if bits else "- (no stack auto-detected)"


def _detect_scripts(repo: Path) -> str:
    out: list[str] = []
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            scripts = json.loads(_read(pkg)).get("scripts", {}) or {}
        except json.JSONDecodeError:
            scripts = {}
        for k, v in sorted(scripts.items()):
            out.append(f"- `npm run {k}` — {v}")
    mk = repo / "Makefile"
    if mk.is_file():
        for line in _read(mk).splitlines():
            m = re.match(r"^([a-zA-Z0-9_\-]+):", line)
            if m and not line.startswith("\t"):
                out.append(f"- `make {m.group(1)}`")
    return "\n".join(out) if out else "- (no scripts auto-detected)"


def _detect_conventions(repo: Path) -> str:
    bits: list[str] = []
    if (repo / "src" / "api").is_dir():
        bits.append("- API routes live under `src/api/`")
    if (repo / "app").is_dir() and (repo / "app" / "main.py").is_file():
        bits.append("- FastAPI entrypoint at `app/main.py`")
    if (repo / "app").is_dir() and (repo / "app" / "page.tsx").is_file():
        bits.append("- Next.js App Router at `app/page.tsx`")
    if (repo / "components").is_dir():
        bits.append("- Reusable React components in `components/`")
    if (repo / "tests").is_dir():
        bits.append("- Tests in `tests/`")
    if (repo / "test").is_dir():
        bits.append("- Tests in `test/`")
    if (repo / "scripts").is_dir():
        bits.append("- Helper scripts in `scripts/`")
    return "\n".join(bits) if bits else "- (no conventions auto-detected)"


def _detect_gotchas(repo: Path) -> str:
    history = repo / ".vibecode" / "run-history.jsonl"
    if not history.is_file():
        return "- (no run-history yet — gotchas will appear after a few runs)"
    counter: Counter[str] = Counter()
    for line in _read(history).splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        err = rec.get("error") or rec.get("err") or rec.get("stderr")
        if not err:
            continue
        # Take the first line as the canonical signature.
        sig = str(err).strip().splitlines()[0][:120]
        counter[sig] += 1
    top = counter.most_common(5)
    if not top:
        return "- (no gotchas accumulated)"
    return "\n".join(f"- ({n}×) `{sig}`" for sig, n in top)


def _detect_test_strategy(repo: Path) -> str:
    bits: list[str] = []
    if (
        (repo / "pytest.ini").is_file()
        or (repo / "pyproject.toml").is_file()
        and "pytest" in _read(repo / "pyproject.toml").lower()
    ):
        bits.append("- **pytest**: `pytest tests/ -v`")
    pkg = repo / "package.json"
    if pkg.is_file():
        text = _read(pkg).lower()
        if '"vitest"' in text:
            bits.append("- **vitest**: `npm run test`")
        if '"jest"' in text:
            bits.append("- **jest**: `npm run test`")
    if (repo / "tests" / "conftest.py").is_file():
        bits.append("- pytest fixtures in `tests/conftest.py`")
    return "\n".join(bits) if bits else "- (no test framework auto-detected)"


_RENDERERS = {
    "stack": _detect_stack,
    "scripts": _detect_scripts,
    "conventions": _detect_conventions,
    "gotchas": _detect_gotchas,
    "test-strategy": _detect_test_strategy,
}


# ---------------------------------------------------------------------------
# Marker manipulation
# ---------------------------------------------------------------------------
def _build_section(name: str, body: str) -> str:
    body = body.strip("\n")
    return f"{_MARKER_BEGIN.format(name=name)}\n" f"{body}\n" f"{_MARKER_END.format(name=name)}"


def _extract_sections(text: str) -> dict[str, str]:
    return {m.group("name"): m.group("body").strip("\n") for m in _MARKER_RE.finditer(text)}


def _replace_section(text: str, name: str, new_body: str) -> str:
    pattern = re.compile(
        rf"<!--\s*vibecode:auto:{re.escape(name)}:begin\s*-->\n?"
        r".*?"
        rf"<!--\s*vibecode:auto:{re.escape(name)}:end\s*-->",
        flags=re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(_build_section(name, new_body), text)
    # Append at end with leading separator.
    sep = "\n\n" if text and not text.endswith("\n\n") else ""
    return text + sep + _build_section(name, new_body) + "\n"


# ---------------------------------------------------------------------------
# MemoryWriteback main class
# ---------------------------------------------------------------------------
class MemoryWriteback:
    """Auto-maintains ``CLAUDE.md`` in a repo (and nested submodules)."""

    def __init__(
        self,
        repo_dir: os.PathLike[str] | str,
        sections: Iterable[str] = _SECTIONS,
        file_name: str = "CLAUDE.md",
    ):
        self.repo = Path(repo_dir).resolve()
        self.sections = tuple(sections)
        self.file_name = file_name

    @property
    def path(self) -> Path:
        return self.repo / self.file_name

    # ---- init / update --------------------------------------------------
    def init(self, *, dry_run: bool = False) -> DiffReport:
        """Create CLAUDE.md from scratch (or no-op if it already exists)."""
        existing = _read(self.path) if self.path.is_file() else ""
        if existing:
            return self.update(dry_run=dry_run)

        body = self._render_full(self.repo)
        if not dry_run:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(body, encoding="utf-8")
        return DiffReport(
            path=self.path,
            sections_added=tuple(self.sections),
            sections_updated=(),
            sections_removed=(),
            bytes_before=0,
            bytes_after=len(body),
            preview=f"+ created {self.path.name} ({len(body)} bytes)",
        )

    def update(self, *, dry_run: bool = False) -> DiffReport:
        """Refresh the auto sections; preserve everything else."""
        before = _read(self.path) if self.path.is_file() else ""
        if not before:
            return self.init(dry_run=dry_run)

        text = before
        added: list[str] = []
        updated: list[str] = []
        existing_sections = _extract_sections(text)

        for name in self.sections:
            new_body = _RENDERERS[name](self.repo)
            if name not in existing_sections:
                text = _replace_section(text, name, new_body)
                added.append(name)
            elif existing_sections[name].strip() != new_body.strip():
                text = _replace_section(text, name, new_body)
                updated.append(name)

        if text != before and not dry_run:
            self.path.write_text(text, encoding="utf-8")

        return DiffReport(
            path=self.path,
            sections_added=tuple(added),
            sections_updated=tuple(updated),
            sections_removed=(),
            bytes_before=len(before),
            bytes_after=len(text),
            preview=self._make_preview(before, text),
        )

    # ---- check (drift) --------------------------------------------------
    def check(self) -> DriftReport:
        """Report which sections are stale, missing, or extraneous."""
        text = _read(self.path) if self.path.is_file() else ""
        existing = _extract_sections(text)
        drifted: list[str] = []
        missing: list[str] = []
        extra: list[str] = []

        for name in self.sections:
            if name not in existing:
                missing.append(name)
                continue
            fresh = _RENDERERS[name](self.repo).strip()
            if existing[name].strip() != fresh:
                drifted.append(name)

        managed = set(self.sections)
        for name in existing:
            if name not in managed:
                extra.append(name)

        return DriftReport(
            path=self.path,
            drifted=tuple(drifted),
            missing=tuple(missing),
            extra=tuple(extra),
        )

    # ---- nested CLAUDE.md ------------------------------------------------
    def nest(self, subpath: str | os.PathLike[str], *, dry_run: bool = False) -> DiffReport:
        """Create a CLAUDE.md scoped to a sub-directory."""
        sub = (self.repo / subpath).resolve()
        if not sub.is_dir():
            raise ValueError(f"nest target not a directory: {sub}")
        if not str(sub).startswith(str(self.repo)):
            raise ValueError(f"nest target escapes repo: {sub}")
        nested = MemoryWriteback(sub, sections=self.sections, file_name=self.file_name)
        return nested.update(dry_run=dry_run)

    # ---- helpers --------------------------------------------------------
    def _render_full(self, repo: Path) -> str:
        head = (
            f"# {repo.name}\n\n"
            "_This file is auto-maintained by VibecodeKit "
            "(`<!-- vibecode:auto:* -->` markers). "
            "Edit OUTSIDE the markers freely; content INSIDE will be "
            "refreshed on each `vibe-memory update`._\n\n"
        )
        sections: list[str] = [head]
        for name in self.sections:
            body = _RENDERERS[name](repo)
            sections.append(
                f"## {name.replace('-', ' ').title()}\n\n" + _build_section(name, body) + "\n"
            )
        return "\n".join(sections)

    @staticmethod
    def _make_preview(before: str, after: str, max_chars: int = 600) -> str:
        if before == after:
            return "(no change)"
        # Compact summary — not a true diff to avoid difflib import here.
        return (
            f"-{len(before)}b\n+{len(after)}b\n"
            f"(showing first {max_chars} of changed file)\n" + after[:max_chars]
        )


__all__ = [
    "MemoryWriteback",
    "DiffReport",
    "DriftReport",
]
