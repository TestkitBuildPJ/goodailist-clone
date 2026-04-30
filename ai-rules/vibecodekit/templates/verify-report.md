# Verify report — <title>

> QA persona writes this.  Focus is on **falsifying** the success claim,
> not confirming it.

## Inputs
- TIP: <link>
- Blueprint: <link to blueprint section + `## 4a. RRI Requirements matrix`>
- Commit range: `<sha>..<sha>`
- Test branch: `<branch>`

## 1. Requirement traceability matrix

> Map every `REQ-*` from the RRI requirements matrix to its current
> implementation status.  Missing rows are auto-failures.

| REQ-ID | Description | Status | Evidence | Owner |
|---|---|---|---|---|
| REQ-001 | <one-line> | DONE / PARTIAL / MISSING / DEFERRED | `path/to/file.ts:42` or `tests/test_foo.py::test_bar` | <name> |
| REQ-002 |  |  |  |  |
| REQ-003 |  |  |  |  |

Status legend:

- **DONE** — implementation present + test asserts behaviour
- **PARTIAL** — implementation present but acceptance criteria not fully met
- **MISSING** — no implementation found (auto-fail)
- **DEFERRED** — explicitly punted to a later TIP (must be linked in blueprint)

## 2. Coverage summary

| Metric | Value |
|---|---|
| Total REQ-* in blueprint | <int> |
| Implemented (DONE) | <int> |
| Partial | <int> |
| Missing | <int> |
| Deferred (excluded from gate) | <int> |
| Coverage % | DONE / (Total − Deferred) |

Release-gate condition: ``Coverage ≥ 85 % AND Missing == 0``.

## 3. Adversarial tests (≥ 3)
| # | Test                                   | Outcome  | Notes                 |
|---|----------------------------------------|----------|-----------------------|
| 1 | <what you tried to break>              | pass/fail|                       |
| 2 |                                        |          |                       |
| 3 |                                        |          |                       |

## 4. Edge cases covered
- [ ] Empty input
- [ ] Malformed input
- [ ] Over-sized input (> budget)
- [ ] Concurrent duplicate request
- [ ] Offline / network failure
- [ ] Permission denied mid-flight
- [ ] Partial state (rollback during commit)

## 5. Regressions
| Area               | Before           | After           | Delta      |
|--------------------|------------------|-----------------|------------|
|                    |                  |                 |            |

## 6. Unverifiable claims
<List every claim you could not falsify with evidence.>

## 7. Scorecard feed-in (per axis)
```json
{
  "a_edge_cases":    {"score": 0.90, "evidence": "6/7 edge cases covered"},
  "a_fail_modes":    {"score": 0.85, "evidence": "3 modes tested"},
  "a_rollback":      {"score": 1.00, "evidence": "git revert tested"},
  "a_accessibility": {"score": 0.95, "evidence": "axe-core 0 violations"}
}
```
