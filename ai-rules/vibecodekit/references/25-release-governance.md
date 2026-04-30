# Release governance

A Vibecode release must pass **all four** gates in order.  Failure at any
gate blocks the release.

## Gate 1 — Quality (7 dims × 8 axes)
Scorecard in `assets/templates/completion-report.md` → fed into
`quality_gate.evaluate()`.  Required:
- every axis ≥ 0.7
- aggregate ≥ 0.85

## Gate 2 — Conformance
`python -m vibecodekit.cli audit --threshold 0.85`.
Required:
- parity ≥ 0.85 (configurable per project)
- no regression vs. previous release's probe results

## Gate 3 — Security
Security auditor attaches `security-note.md`:
- list of newly introduced tool-classifications (especially class 3/4)
- any override of the permission matrix
- any `bypass --unsafe` invocation is a red flag and requires explicit
  justification + sign-off

## Gate 4 — Operator confirmation
Final YES/NO from the operator.  The gate records the decision and the
rationale into `.vibecode/runtime/release.json` with a timestamp.

## Release artifacts

| Artifact                 | Location                                  |
|--------------------------|-------------------------------------------|
| Completion report        | `docs/completion-<version>.md`            |
| Verify report            | `docs/verify-<version>.md`                |
| Security note            | `docs/security-<version>.md`              |
| Audit output             | `.vibecode/runtime/audit-<version>.json`  |
| Release decision         | `.vibecode/runtime/release.json`          |
