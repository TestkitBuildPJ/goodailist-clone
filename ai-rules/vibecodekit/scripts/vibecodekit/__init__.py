"""VibecodeKit Hybrid Ultra — Full Agentic OS Runtime + Methodology Overlay.

Runtime layer: 30 probes corresponding 1:1 to the architectural patterns from
"Giải phẫu một Agentic Operating System" (Lâm Nguyễn, 2026) —
async generator loop, five-layer context defence, 7 task kinds,
4-phase DreamTask, MCP stdio, 33 hook events, cost ledger,
cross-platform (fcntl/msvcrt) locked denial store, 3-tier memory
hierarchy with pluggable embedding, approval/elicitation JSON contract,
follow-up re-execute loop, conditional skill activation.

Methodology layer: 9 extra probes exercising RRI (Reverse Requirements
Interview), RRI-T (7-dim testing × 8-stress-axis), RRI-UX (Flow Physics),
RRI-UI (4-phase pipeline), VIBECODE-MASTER workflow, Vietnamese
12-item checklist, and the 6 methodology slash-commands.

Public API is exposed via the ``cli`` module (``python -m vibecodekit.cli``)
and via the command-line scripts installed under ``ai-rules/vibecodekit/bin``.

Version resolution:

``__version__`` is single-sourced from the bundle's ``VERSION`` file
(same directory as ``SKILL.md``).  When ``VERSION`` cannot be found
(e.g. a partial copy without the bundle root), falls back to
``importlib.metadata`` (works when installed via ``pip install``).
If neither source is available the module raises ``RuntimeError``
so stale hard-coded fallbacks never ship silently.

Use ``vibecodekit.VERSION`` or ``vibecodekit.__version__`` for the
resolved value.
"""

from __future__ import annotations

from pathlib import Path as _Path


def _resolve_version() -> str:
    """Resolve version from bundle's ``VERSION`` file.

    Walks upward from this module's directory looking for a ``VERSION``
    file co-located with ``SKILL.md`` (i.e. the skill bundle root).
    Falls back to ``importlib.metadata`` when installed as a package.
    """
    here = _Path(__file__).resolve().parent  # .../scripts/vibecodekit
    candidates = [
        here.parent.parent / "VERSION",  # skill/vibecodekit-hybrid-ultra/VERSION
        here.parent.parent.parent / "VERSION",  # repo root VERSION (dev checkout)
    ]
    for p in candidates:
        try:
            if p.is_file():
                v = p.read_text(encoding="utf-8").strip()
                if v:
                    return v
        except OSError:
            continue

    # Fallback: installed via pip — version comes from package metadata.
    try:
        from importlib.metadata import version as _pkg_version

        return _pkg_version("vibecodekit-hybrid-ultra")
    except Exception:
        pass

    raise RuntimeError(
        "Cannot determine vibecodekit version: no VERSION file found "
        "and package is not installed.  Run from the repo root or "
        "install via `pip install -e .`."
    )


__version__ = _resolve_version()
VERSION = __version__

__all__ = ["__version__", "VERSION"]
