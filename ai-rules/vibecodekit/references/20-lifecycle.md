# Vibecode lifecycle — 8 steps, 10 terminal states

## The 8 steps

1. **Blueprint** — write a one-page architecture summary; identify entities,
   data flows, invariants, success metrics.  Template:
   `assets/templates/blueprint.md`.
2. **Scan** — explore the repo in read-only mode (scout role); produce
   `scan-report.md`.
3. **TIP (Task Instruction Pack)** — a signed-off, narrowly-scoped
   statement of what will change, why, rollback plan, risk class.  Template:
   `assets/templates/tip.md`.
4. **Execute** — run `python -m vibecodekit.cli run <plan.json>`.  All tool
   uses pass through the 6-layer permission pipeline.
5. **Verify** — QA role runs adversarial tests; verify-report confirms what
   was falsified, what survived (template:
   `assets/templates/verify-report.md`).
6. **Complete** — file a completion report summarising artefacts, decisions,
   outstanding risks (template:
   `assets/templates/completion-report.md`).
7. **Conform** — run `python -m vibecodekit.cli audit --threshold 0.85`;
   attach the JSON output.
8. **Release gate** — feed scorecard into `quality_gate.evaluate()`; the
   Compliance Steward signs off if `passed: true`.

## 10 terminal states observable in the event log

| # | Event                                   | Meaning                                 |
|---|-----------------------------------------|-----------------------------------------|
| 1 | `query_end` status=ok                   | plan exhausted cleanly                  |
| 2 | `query_end` status=error                | unrecoverable failure                   |
| 3 | `terminal_error`                        | recovery ladder exhausted               |
| 4 | `recovery_ask_user`                     | waiting for human decision              |
| 5 | `batch_abort`                           | exclusive batch aborted after failure   |
| 6 | `subagent_stop`                         | sub-agent finished                      |
| 7 | `compact_done`                          | context defense finished this turn      |
| 8 | `recovery_compact`                      | reactive compact ran during recovery    |
| 9 | `context_modifier_applied`              | state mutated after a batch             |
|10 | `denial_recorded`                       | permission engine recorded a denial     |

These are the **only** states that downstream consumers (dashboards,
alerting, compliance audits) are required to understand.
