# Completion report — <title>

## Summary
<≤ 200 words; what shipped, why, who signed off.>

## Artifacts
- TIP: <link>
- PR / commit: <sha>
- Verify report: <link>
- Security note (if Class 3/4): <link>

## Scorecard (fed to quality_gate.evaluate)
```json
{
  "d_correctness":      {"score": 0.95, "evidence": "pytest green, 87% coverage"},
  "d_reliability":      {"score": 0.90, "evidence": "retry + circuit breaker tested"},
  "d_security":         {"score": 0.92, "evidence": "audit doc, no new tool classes 3/4"},
  "d_performance":      {"score": 0.85, "evidence": "p95 < 200ms local"},
  "d_maintainability":  {"score": 0.88, "evidence": "docstrings + 105 tests"},
  "d_observability":    {"score": 0.90, "evidence": "event bus milestones present"},
  "d_ux_clarity":       {"score": 0.85, "evidence": "CLI --help complete"},
  "a_intent_fit":       {"score": 1.00, "evidence": "matches TIP exactly"},
  "a_scope_fit":        {"score": 0.95, "evidence": "no files outside declared scope"},
  "a_edge_cases":       {"score": 0.90, "evidence": "6/7 covered"},
  "a_fail_modes":       {"score": 0.85, "evidence": "3 modes documented + tested"},
  "a_rollback":         {"score": 1.00, "evidence": "git revert tested"},
  "a_privacy":          {"score": 1.00, "evidence": "no PII surfaced"},
  "a_accessibility":    {"score": 0.90, "evidence": "WCAG 2.2 AA"},
  "a_cost":             {"score": 0.90, "evidence": "no new cloud calls"}
}
```

## Aggregate
<fill in from `python -m vibecodekit.quality_gate completion-report.json`>

## Outstanding risks
| Risk | Severity | Owner | Target |
|------|:--------:|-------|--------|
|      |          |       |        |

## Release decision
- [ ] PROCEED
- [ ] BLOCK — reason: <...>
