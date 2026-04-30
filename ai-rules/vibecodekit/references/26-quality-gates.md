# Quality gates — 7 dimensions × 8 axes

## 7 dimensions (how "good" the change is)

| Dimension         | Key question                                                              |
|-------------------|---------------------------------------------------------------------------|
| d_correctness     | Does it produce the right output for the documented inputs?               |
| d_reliability     | Does it handle transient failures, timeouts, partial data?                |
| d_security        | Does it preserve confidentiality, integrity, authz boundaries?            |
| d_performance     | Does it meet budget (latency, memory, cost)?                              |
| d_maintainability | Can a new engineer change it safely within a week?                        |
| d_observability   | Can operators diagnose a live incident in ≤ 15 min?                       |
| d_ux_clarity      | Do end-users understand the output / UI at a glance?                      |

## 8 axes (how well we verified the change)

| Axis                | Rubric                                                                  |
|---------------------|-------------------------------------------------------------------------|
| a_intent_fit        | Does the change match the TIP's stated intent, nothing more/less?       |
| a_scope_fit         | No scope creep; no unrelated refactors bundled in.                      |
| a_edge_cases        | ≥ 3 edge cases covered (empty, malformed, over-sized).                  |
| a_fail_modes        | Every catastrophic failure documented + tested.                         |
| a_rollback          | Revertible via `git revert` or a documented procedure.                  |
| a_privacy           | No new PII surfaced without explicit consent UX.                        |
| a_accessibility     | WCAG 2.2 AA for any UI; keyboard + screen-reader friendly.              |
| a_cost              | Runtime cost bounded; no unbounded loops, no unreviewed cloud calls.    |

## Scorecard format
A JSON object where each of the 7 + 8 = 15 keys has:
```json
{
  "score": 0.92,
  "evidence": "pytest/test_foo.py::test_bar; 17/17 pass; p95 < 200ms"
}
```

Feed to `quality_gate.evaluate(scorecard)` to receive the verdict.  CI
should fail the release job if `passed` is false.

## Rubric defaults
- `MIN_AXIS = 0.70` — any axis below this blocks release.
- `MIN_AGGREGATE = 0.85` — aggregate average blocks release.

Override per project via env vars or CLI flags in a future release.
