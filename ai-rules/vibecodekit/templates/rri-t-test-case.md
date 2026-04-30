# RRI-T Test Case — <title>

> Q→A→R→P→T format.  One file per test case, or append under a `# Test Suite`
> document.  See `references/31-rri-t-testing.md` for full methodology.

---

## ID
`<MODULE>-<DIMENSION>-<NUMBER>`   (e.g. `BUDGET-D4-017`)

## Persona
`[ 👤 End User | 📋 Business | 🔍 QA | 🛠️ DevOps | 🔒 Security ]`

## Q — Câu hỏi (persona point-of-view)
<Single, specific question from this persona's perspective.>

## A — Expected behaviour
<What should actually happen, observable externally.>

## R — Requirement rút ra
<Maps back to `REQ-NNN` from the RRI matrix, or flags as MISSING.>

## P — Priority
`[ P0 (ship blocker) | P1 (must-fix-before-GA) | P2 (nice) | P3 (backlog) ]`

## T — Test case

### Precondition
- <state the system must be in>
- <seed data if any>

### Steps
1. <explicit action, testable>
2. <explicit action>
3. <explicit action>

### Expected
<Detailed, falsifiable outcome — include visible messages, DB state,
HTTP status, response JSON shape.>

### Dimension
`[ D1 UI/UX | D2 API | D3 Performance | D4 Security | D5 Data | D6 Infra | D7 Edge ]`

### Stress axes
`[ TIME | DATA | ERROR | COLLAB | EMERGENCY | SECURITY | INFRASTRUCTURE | LOCALIZATION ]`
(Combine 1-3 axes for a real stress scenario.)

---

## Result
`[ ✅ PASS | ❌ FAIL | ⚠️ PAINFUL | 🔲 MISSING ]`

### Notes
<Evidence — log excerpt, screenshot link, curl -v output, stack trace.>
