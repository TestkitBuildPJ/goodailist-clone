# TIP — <title>

> A Task Instruction Pack is the unit of execution.  Keep it narrow.
> One TIP = one mergeable PR.

## SVPFI
- **Scope:** <≤ 280 chars, single string; files / endpoints / modules>
- **Verification:** <what's already verified; what remains (adversarial test required)>
- **Principles:** <invariants the change must preserve — link to blueprint>
- **Failure modes:** <≥ 3 scenarios: what can break and how we detect it>
- **Interfaces:** <new signatures / schemas / wire formats, or "NO-CHANGE">

## Risk class (1..4)
- [ ] Class 1 — read-only / additive; no user-visible change.
- [ ] Class 2 — schema-compatible mutation (append-only).
- [ ] Class 3 — behaviour change in a single module.
- [ ] Class 4 — cross-cutting / security-sensitive / DB migration.

Class 3/4 require Security Auditor sign-off.

## Execution plan
```json
{
  "turns": [
    {"tool_uses": [
      {"tool": "list_files", "input": {"path": "."}}
    ]}
  ]
}
```

## Rollback
<exact command or PR revert pattern>

## Acceptance criteria
1. <falsifiable statement>
2. <falsifiable statement>

## Sign-off
- Implementation Lead: <date>
- Security Auditor (if Class 3/4): <date>
