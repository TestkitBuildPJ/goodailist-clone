"""Five-layer context defense (Pattern #9).

Giải phẫu §8 distinguishes:

    1.  Tool-result truncation    (~free)
    2.  Microcompact              (no LLM call — drop stale tool results)
    3.  Auto-compact              (proactive LLM summarise at turn boundary)
    4.  Reactive-compact          (after prompt_too_long / 413)
    5.  Context collapse          (read-time projection keeping a minimal core)

In v0.7 all five layers are *functional* — they actually produce artefacts on
disk (we don't call an LLM, so "summarise" means "drop all payload bodies and
keep one-liner event descriptors").  Layers 4 & 5 were stubs in v0.6.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_CHARS = 40_000
CRITICAL_MAX_CHARS = 120_000  # triggers reactive + collapse

# Stable "keeps" — the minimum we promise to carry across compactions.
_COLLAPSE_KEEPS = [
    "blueprint",
    "requirements",
    "decision_log",
    "active_tip",
    "risks",
    "security_constraints",
    "business_rules",
    "latest_observations",
    "open_questions",
    "release_decision",
]


def _runtime_dir(root: Path) -> Path:
    d = root / ".vibecode" / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _collect_events(rt: Path) -> list[str]:
    events: list[str] = []
    for f in sorted(rt.glob("*.events.jsonl")):
        try:
            events.extend(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            continue
    return events


def _summarise_line(line: str) -> dict[str, Any] | None:
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None
    return {
        "ts": rec.get("ts"),
        "event": rec.get("event"),
        "status": rec.get("status"),
        "turn": rec.get("turn"),
        "payload_keys": list((rec.get("payload") or {}).keys()),
    }


def _load_keeps(root: Path) -> dict[str, Any]:
    """Gather 'keep' facts from standard project files, if present."""
    keeps: dict[str, Any] = {}
    candidates = {
        "blueprint": ["BLUEPRINT.md", "docs/BLUEPRINT.md", ".vibecode/BLUEPRINT.md"],
        "requirements": ["REQUIREMENTS.md", "docs/REQUIREMENTS.md", ".vibecode/REQUIREMENTS.md"],
        "decision_log": ["DECISIONS.md", "docs/DECISIONS.md", ".vibecode/decision-log.md"],
        "active_tip": [".vibecode/active-tip.md"],
        "risks": ["RISKS.md", "docs/RISKS.md", ".vibecode/RISKS.md"],
    }
    for k, paths in candidates.items():
        for rel in paths:
            p = root / rel
            if p.exists() and p.is_file():
                try:
                    txt = p.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                keeps[k] = {"path": rel, "bytes": len(txt), "head": txt[:400]}
                break
    return keeps


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def compact(
    root: str | os.PathLike = ".", *, reactive: bool = False, max_chars: int = DEFAULT_MAX_CHARS
) -> dict[str, Any]:
    """Run layers 1-3 always, and layers 4-5 if ``reactive`` or ``raw_chars >= CRITICAL``.

    Returns a dict describing what was done.  Always deterministic: safe to
    call repeatedly per turn.
    """
    root = Path(root).resolve()
    rt = _runtime_dir(root)
    events = _collect_events(rt)
    raw = "\n".join(events)
    out: dict[str, Any] = {"raw_chars": len(raw), "layers": []}

    # --- Layer 1 — Tool-result truncation ---------------------------------
    if len(raw) > max_chars:
        artifact = rt / "tool-results.truncated.txt"
        artifact.write_text(raw[:-max_chars], encoding="utf-8")
        raw = raw[-max_chars:]
        out["layers"].append(
            {
                "layer": 1,
                "name": "tool_result_truncation",
                "artifact": str(artifact.relative_to(root)),
            }
        )

    # --- Layer 2 — Microcompact -------------------------------------------
    lines = raw.splitlines()
    summaries = [s for s in (_summarise_line(l) for l in lines[-500:]) if s]
    out["layers"].append({"layer": 2, "name": "microcompact", "events_kept": len(summaries)})

    # --- Layer 3 — Auto-compact (boundary artefact) -----------------------
    summary_text = json.dumps(summaries, ensure_ascii=False, indent=2)
    boundary = rt / "compact-boundary.json"
    boundary.write_text(
        json.dumps(
            {
                "schema": "vibe.compact-boundary/1",
                "created_ts": time.time(),
                "summary_chars": len(summary_text),
                "summary": summary_text[-20_000:],
                "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    out["layers"].append(
        {"layer": 3, "name": "auto_compact", "boundary": str(boundary.relative_to(root))}
    )

    # --- Layer 4 — Reactive compact ---------------------------------------
    trigger_reactive = reactive or len(raw) >= CRITICAL_MAX_CHARS
    if trigger_reactive:
        reactive_path = rt / "reactive-compact.json"
        reactive_path.write_text(
            json.dumps(
                {
                    "schema": "vibe.reactive-compact/1",
                    "trigger": "reactive" if reactive else "critical_size",
                    "events_dropped": max(0, len(lines) - 100),
                    "events_kept": min(100, len(lines)),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # Truncate the jsonl files: keep only the last 100 events spread
        # across new per-session files so downstream dashboards still work.
        kept = lines[-100:]
        for f in rt.glob("*.events.jsonl"):
            f.unlink(missing_ok=True)
        if kept:
            new = rt / f"vibe-reactive-{int(time.time())}.events.jsonl"
            new.write_text("\n".join(kept) + "\n", encoding="utf-8")
        out["layers"].append(
            {
                "layer": 4,
                "name": "reactive_compact",
                "artifact": str(reactive_path.relative_to(root)),
                "events_kept": len(kept),
            }
        )

    # --- Layer 5 — Context collapse (read-time projection) ---------------
    keeps = _load_keeps(root)
    collapse = {
        "schema": "vibe.collapse/1",
        "keeps_definition": _COLLAPSE_KEEPS,
        "keeps_collected": keeps,
        "created_ts": time.time(),
    }
    collapse_path = rt / "context-collapse.json"
    collapse_path.write_text(json.dumps(collapse, ensure_ascii=False, indent=2), encoding="utf-8")
    out["layers"].append(
        {
            "layer": 5,
            "name": "context_collapse",
            "artifact": str(collapse_path.relative_to(root)),
            "keeps": sorted(keeps.keys()),
        }
    )
    return out
