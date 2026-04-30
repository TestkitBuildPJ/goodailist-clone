# Permission matrix by role

This is the **canonical role → permission** mapping enforced by
`subagent_runtime.PROFILES` and the permission engine.

| Role        | Mode default | FileRead | FileWrite | Bash (read) | Bash (mut) | Agent spawn | Net fetch |
|-------------|:------------:|:--------:|:---------:|:-----------:|:----------:|:-----------:|:---------:|
| coordinator | plan         | ✓        | —         | —           | —          | ✓           | —         |
| scout       | plan         | ✓        | —         | ✓           | —          | —           | ✓ (read)  |
| builder     | default      | ✓        | ✓         | ✓           | ✓ (ask)    | ✓           | ✓         |
| qa          | plan         | ✓        | —         | ✓           | —          | —           | ✓         |
| security    | plan         | ✓        | —         | ✓           | —          | —           | ✓         |

Legend: ✓ = always allowed; — = refused; "ask" = requires user decision.

## Escalation path (bubble)

Child agents spawned from a parent run in `bubble` mode: the permission
engine returns `decision=ask` and records a `bubble_request` event on the
parent's stream.  The parent is expected to resolve the request (allow or
deny) before the child can proceed.

## Override & auditing
- Users may override the matrix via `.vibecode/rules.json` (see Layer 3 of
  the pipeline).
- Every override is logged to the event bus as a `permission_decision`
  event with the matching rule id.
