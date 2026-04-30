"""pipeline_router — master router for the 3 VCK-HU pipelines.

This is the runtime backing the ``/vck-pipeline`` slash command (T6 of
``docs/INTEGRATION-PLAN-v0.15.md``).  Every prose request the operator
types in the host LLM is classified into one of three pipelines that
**actually run end-to-end** in the v0.15.0-alpha overlay:

* **A. PROJECT CREATION** — bootstrap a brand-new project.  Routes to
  ``/vibe-scaffold`` (which now seeds ``.vibecode/`` automatically per
  T5) followed by ``/vibe-blueprint``.
* **B. FEATURE DEV** — build a feature in an existing project.  Routes
  to ``/vibe-run`` (security classifier auto-on per T4) followed by
  ``/vck-ship`` (team-mode preflight + eval_select per T1 + T2).
* **C. CODE & SECURITY** — audit / harden existing code.  Routes to
  ``/vck-cso`` + ``/vck-review``.

The router is intentionally simple.  It uses a small VN + EN keyword
bank — exactly the same shape as :mod:`intent_router` — so any
operator who is comfortable with ``/vibe`` will be comfortable with
``/vck-pipeline`` too.  When confidence is too low, it falls back to
asking a clarifying question instead of guessing.

Public API::

    from vibecodekit.pipeline_router import PipelineRouter
    r = PipelineRouter()
    decision = r.route("làm cho tôi shop online bán cà phê")
    # decision.pipeline == "A"
    # decision.commands == ("/vibe-scaffold", "/vibe-blueprint")

Design invariants:

1. The router is **read-only** — it never executes commands.  It just
   returns the canonical sequence the host should run.
2. Every command in every pipeline is currently wired into the
   manifest + intent_router (so audit Probe #79 stays green).
3. The keyword bank is short by design.  Adding a keyword requires a
   matching test; see :mod:`tests.test_pipeline_router`.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

__all__ = [
    "Pipeline",
    "PipelineDecision",
    "PipelineRouter",
    "PIPELINES",
]


# ---------------------------------------------------------------------------
# Pipeline definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pipeline:
    code: str  # "A" | "B" | "C"
    name: str
    description: str
    commands: tuple[str, ...]
    keywords: tuple[str, ...]


PIPELINES: tuple[Pipeline, ...] = (
    Pipeline(
        code="A",
        name="PROJECT CREATION",
        description=(
            "Bootstrap a brand-new project.  Runs /vibe-scaffold "
            "(seeds .vibecode/ runtime context per T5) followed by "
            "/vibe-blueprint to lock the architecture."
        ),
        commands=("/vibe-scaffold", "/vibe-blueprint"),
        keywords=(
            # English
            "new project",
            "scaffold",
            "bootstrap",
            "start project",
            "create project",
            "initialize",
            "init project",
            "kick off",
            "greenfield",
            "from scratch",
            # v0.16.0-α — P3 #9 EN equivalents that bias toward A.
            "build the whole thing",
            "set everything up",
            # Vietnamese
            "dự án mới",
            "du an moi",
            "tạo dự án",
            "tao du an",
            "khởi tạo",
            "khoi tao",
            "bắt đầu dự án",
            "bat dau du an",
            "làm cho tôi",
            "lam cho toi",
            "xây dựng từ đầu",
            "xay dung tu dau",
            "shop online",
            "landing page",
        ),
    ),
    Pipeline(
        code="B",
        name="FEATURE DEV",
        description=(
            "Build a feature in an existing project.  Runs /vibe-run "
            "(security classifier auto-on per T4) followed by "
            "/vck-ship (team-mode preflight + eval_select)."
        ),
        commands=("/vibe-run", "/vck-ship"),
        keywords=(
            # English
            "add feature",
            "implement feature",
            "new feature",
            "build feature",
            "ship feature",
            "fix bug",
            "patch",
            "update",
            "improve",
            # v0.16.0-α — P2 #4 + P3 #9 "go-through-the-whole-pipeline"
            # phrases.  Routed to FEATURE DEV per audit recommendation
            # (the "checked-everything" feel maps to /vibe-run → /vck-ship).
            "full check",
            "all gates",
            "end to end",
            "e2e check",
            "go through pipeline",
            "pipeline đầy đủ",
            "pipeline day du",
            # Vietnamese
            "tính năng mới",
            "tinh nang moi",
            "thêm tính năng",
            "them tinh nang",
            "phát triển tính năng",
            "phat trien tinh nang",
            "sửa lỗi",
            "sua loi",
            "cập nhật",
            "cap nhat",
            "cải thiện",
            "cai thien",
        ),
    ),
    Pipeline(
        code="C",
        name="CODE & SECURITY",
        description=(
            "Audit / harden existing code.  Runs /vck-cso (OWASP + "
            "STRIDE) followed by /vck-review (multi-perspective adversarial)."
        ),
        commands=("/vck-cso", "/vck-review"),
        keywords=(
            # English
            "audit",
            "review",
            "security",
            "harden",
            "vulnerability",
            "owasp",
            "stride",
            "code review",
            "audit code",
            "check security",
            "security audit",
            "pen test",
            # Vietnamese
            "kiểm tra bảo mật",
            "kiem tra bao mat",
            "review code",
            "đánh giá bảo mật",
            "danh gia bao mat",
            "soát code",
            "soat code",
            "bảo mật",
            "bao mat",
            "lỗ hổng",
            "lo hong",
        ),
    ),
)


@dataclass(frozen=True)
class PipelineDecision:
    pipeline: str | None  # "A" | "B" | "C" | None when below threshold
    name: str | None
    commands: tuple[str, ...]
    confidence: float  # 0.0 .. 1.0
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)
    needs_clarification: bool = False
    explain: str = ""

    def as_dict(self) -> dict:
        return {
            "pipeline": self.pipeline,
            "name": self.name,
            "commands": list(self.commands),
            "confidence": round(self.confidence, 3),
            "matched_keywords": list(self.matched_keywords),
            "needs_clarification": self.needs_clarification,
            "explain": self.explain,
        }


_NORMALIZE_RE = re.compile(r"\s+")


def _normalize(s: str) -> str:
    return _NORMALIZE_RE.sub(" ", s.strip().lower())


class PipelineRouter:
    """Classify a free-form prose request into one of the 3 pipelines.

    Confidence is computed as ``min(1.0, len(matched_keywords) / 2)``
    so a single very-specific match (e.g. "owasp") is still confident,
    while two generic words ("update fix") give the same score.

    The threshold for ``needs_clarification`` is 0.5 — anything below
    is reported as low-confidence with the top-2 candidate pipelines.
    """

    LOW_CONF_THRESHOLD = 0.5

    def __init__(self, pipelines: Sequence[Pipeline] = PIPELINES) -> None:
        self._pipelines = tuple(pipelines)

    def route(self, prose: str) -> PipelineDecision:
        text = _normalize(prose)
        if not text:
            return PipelineDecision(
                pipeline=None,
                name=None,
                commands=(),
                confidence=0.0,
                needs_clarification=True,
                explain="empty input — please describe what you want to do",
            )
        # Score each pipeline by counting keyword hits.
        scores: list[tuple[Pipeline, list[str]]] = []
        for p in self._pipelines:
            hits = [kw for kw in p.keywords if kw in text]
            scores.append((p, hits))
        scores.sort(key=lambda pair: len(pair[1]), reverse=True)
        top, top_hits = scores[0]
        confidence = min(1.0, len(top_hits) / 2.0)
        if confidence < self.LOW_CONF_THRESHOLD:
            # Low confidence → ask the operator to clarify.
            top2 = [p.code for p, _ in scores[:2] if p.code != top.code]
            return PipelineDecision(
                pipeline=None,
                name=None,
                commands=(),
                confidence=confidence,
                matched_keywords=tuple(top_hits),
                needs_clarification=True,
                explain=(
                    "low confidence — please pick a pipeline: " + ", ".join([top.code] + top2)
                ),
            )
        return PipelineDecision(
            pipeline=top.code,
            name=top.name,
            commands=top.commands,
            confidence=confidence,
            matched_keywords=tuple(top_hits),
            needs_clarification=False,
            explain=(
                f"matched pipeline {top.code} ({top.name}) "
                f"on keywords: {', '.join(top_hits) or '(none)'}"
            ),
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Master router for the 3 VCK-HU pipelines (A/B/C).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rt = sub.add_parser("route", help="Classify prose into a pipeline.")
    rt.add_argument("prose", nargs="+", help="Free-form prose request (VN or EN).")

    sub.add_parser("list", help="List the 3 pipelines.")

    args = ap.parse_args(argv)
    router = PipelineRouter()

    if args.cmd == "route":
        decision = router.route(" ".join(args.prose))
        print(json.dumps(decision.as_dict(), ensure_ascii=False, indent=2))
        return 0 if decision.pipeline else 2
    if args.cmd == "list":
        out = [
            {
                "code": p.code,
                "name": p.name,
                "description": p.description,
                "commands": list(p.commands),
                "n_keywords": len(p.keywords),
            }
            for p in PIPELINES
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
