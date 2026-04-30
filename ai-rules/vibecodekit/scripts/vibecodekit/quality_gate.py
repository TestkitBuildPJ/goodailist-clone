"""Quality gate — 7 dimensions × 8 axes produce a release score.

The dimensions and axes are documented in references/26-quality-gates.md.
Here we provide a pure function that takes a scorecard dict and returns a
single pass/fail verdict with per-axis justifications.

A scorecard entry looks like::

    {
      "d_correctness": {"score": 0.9, "evidence": "pytest green"},
      ...
    }

Default rubric is fail-if-any-axis < 0.7 OR aggregate < 0.85.

References:
- ``references/25-release-governance.md``
"""

from __future__ import annotations

import argparse
import json
from typing import Any

DIMENSIONS = [
    "d_correctness",
    "d_reliability",
    "d_security",
    "d_performance",
    "d_maintainability",
    "d_observability",
    "d_ux_clarity",
]
AXES = [
    "a_intent_fit",
    "a_scope_fit",
    "a_edge_cases",
    "a_fail_modes",
    "a_rollback",
    "a_privacy",
    "a_accessibility",
    "a_cost",
]

MIN_AXIS = 0.7
MIN_AGGREGATE = 0.85


def evaluate(
    scorecard: dict[str, Any], *, min_axis: float = MIN_AXIS, min_aggregate: float = MIN_AGGREGATE
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total = 0.0
    count = 0
    failed_below_min: list[str] = []
    for key in DIMENSIONS + AXES:
        row = scorecard.get(key) or {}
        score = float(row.get("score", 0.0))
        total += score
        count += 1
        rows.append({"key": key, "score": round(score, 3), "evidence": row.get("evidence", "")})
        if score < min_axis:
            failed_below_min.append(key)
    aggregate = total / count if count else 0.0
    passed = (not failed_below_min) and (aggregate >= min_aggregate)
    return {
        "passed": passed,
        "aggregate": round(aggregate, 3),
        "min_axis": min_axis,
        "min_aggregate": min_aggregate,
        "failed_below_min": failed_below_min,
        "rows": rows,
    }


def _main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate a scorecard JSON.")
    ap.add_argument("scorecard")
    args = ap.parse_args()
    with open(args.scorecard, encoding="utf-8") as f:
        sc = json.load(f)
    out = evaluate(sc)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
