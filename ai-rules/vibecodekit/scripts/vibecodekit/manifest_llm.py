"""LLM-introspection manifest generator (v0.11.0, audit round 6).

Produces ``manifest.llm.json``: a single self-contained file an LLM
(Claude / Devin / etc.) can read to discover *everything* the kit
exposes — slash commands, sub-agent roles, hooks, references and the
auto-maintenance hooks for memory.

The manifest is generated from canonical sources:

1. ``assets/plugin-manifest.json``    — commands / agents / hooks lists
2. ``SKILL.md``                       — frontmatter (name, version,
                                         when_to_use, triggers, paths)
3. ``references/*.md``                — title (first H1) per reference

Compared to plugin-manifest.json, this manifest adds:
- ``introspection`` block: exact paths an LLM should read first
- ``references`` array: title + path for every spec doc
- ``memory`` block: writeback command + auto-trigger hook list

References:
- ``references/00-overview.md``
- ``references/24-memory-governance.md``
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_FRONT_RX = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_H1_RX = re.compile(r"^# (.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> dict[str, Any]:
    m = _FRONT_RX.search(text)
    if not m:
        return {}
    block = m.group(1)
    out: dict[str, Any] = {}
    key: str | None = None
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


def _ref_title(text: str, fallback: str) -> str:
    m = _H1_RX.search(text)
    if m:
        return m.group(1).strip()
    return fallback


def build_manifest(skill_root: Path) -> dict[str, Any]:
    """Construct the manifest dict for a given skill root.

    ``skill_root`` should point at the directory containing ``SKILL.md``
    and ``assets/plugin-manifest.json`` (e.g. the skill bundle root).
    """
    skill_root = Path(skill_root).resolve()
    plugin_manifest_path = skill_root / "assets" / "plugin-manifest.json"
    skill_md_path = skill_root / "SKILL.md"
    references_dir = skill_root / "references"

    if not plugin_manifest_path.is_file():
        raise FileNotFoundError(f"plugin-manifest.json not found at {plugin_manifest_path}")
    plugin = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))

    skill_fm: dict[str, Any] = {}
    if skill_md_path.is_file():
        skill_fm = _parse_frontmatter(skill_md_path.read_text(encoding="utf-8"))

    refs: list[dict[str, str]] = []
    if references_dir.is_dir():
        for ref_path in sorted(references_dir.glob("*.md")):
            text = ref_path.read_text(encoding="utf-8")
            refs.append(
                {
                    "id": ref_path.stem,
                    "title": _ref_title(text, ref_path.stem),
                    "path": f"references/{ref_path.name}",
                }
            )

    return {
        "$schema": "https://vibecodekit.dev/schema/manifest-llm-0.11.json",
        "kind": "vibecodekit.manifest.llm",
        "name": plugin.get("name", skill_fm.get("name", "unknown")),
        "version": plugin.get("version", skill_fm.get("version", "0.0.0")),
        "description": skill_fm.get("description", ""),
        "introspection": {
            "skill_md": "SKILL.md",
            "plugin_manifest": "assets/plugin-manifest.json",
            "frontmatter_keys": [
                "name",
                "version",
                "description",
                "when_to_use",
                "triggers",
                "paths",
            ],
            "discovery_module": "vibecodekit.skill_discovery",
        },
        "skill_frontmatter": {
            "when_to_use": skill_fm.get("when_to_use", ""),
            "triggers": skill_fm.get("triggers", []),
            "paths": skill_fm.get("paths", []),
        },
        "commands": plugin.get("commands", []),
        "agents": plugin.get("agents", []),
        "hooks": plugin.get("hooks", []),
        "servers": plugin.get("servers", []),
        "references": refs,
        "memory": {
            "writeback_module": "vibecodekit.memory_writeback",
            "writeback_command": "memory writeback update",
            "auto_writeback_module": "vibecodekit.auto_writeback",
            "auto_writeback_command": "memory writeback auto",
            "auto_trigger_hooks": ["session_start"],
            "default_interval_seconds": 1800,
            "opt_out_marker": ".vibecode/auto_writeback_disabled",
        },
        "runtime": {
            "cli_entrypoint": "python -m vibecodekit.cli",
            "scripts_module": "vibecodekit",
        },
    }


def emit(skill_root: Path, output: Path | None = None, indent: int = 2) -> Path:
    """Build + write the manifest. Returns the written path."""
    manifest = build_manifest(skill_root)
    out = output or (Path(skill_root).resolve() / "manifest.llm.json")
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    return out


def _main() -> int:
    ap = argparse.ArgumentParser(description="Emit manifest.llm.json from skill root.")
    ap.add_argument("--root", default=".", help="Skill bundle root (contains SKILL.md + assets/)")
    ap.add_argument("--output", default=None, help="Output path (default <root>/manifest.llm.json)")
    args = ap.parse_args()
    out = emit(Path(args.root), Path(args.output) if args.output else None)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
