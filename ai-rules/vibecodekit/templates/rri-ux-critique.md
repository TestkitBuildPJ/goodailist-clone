# RRI-UX Critique — <title>

> S→V→P→F→I format.  One entry per issue, append to a single
> `ux-critique.md` per module.  See `references/32-rri-ux-critique.md`.

---

## ID
`<MODULE>-<DIMENSION>-<NUMBER>`   (e.g. `APPROVALS-U1-004`)

## Persona
`[ 🏃 Speed Runner | 👁️ First-Timer | 📊 Data Scanner | 🔄 Multi-Tasker | 📱 Field Worker ]`

## S — Scenario (persona's actual task)
<In one or two sentences, describe what the persona is trying to do
and the state they are in.  Avoid framing it as "the user clicks X".>

## V — Violation
<What is wrong — observable, specific.>
<Write "None — FLOW" if this scenario is clean.>

## P — Physics axis + Dimension violated
- **Flow Physics axis:** `SCROLL | CLICK-DEPTH | EYE-TRAVEL | DECISION-LOAD | RETURN-PATH | VIEWPORT | VN-TEXT | FEEDBACK`
- **UX dimension:**      `U1 Flow | U2 Hierarchy | U3 Cognitive | U4 Feedback | U5 Error | U6 Accessibility | U7 Context`

## F — Fix (concrete)
<Down to the component / CSS / route level if possible.  Not "improve
feedback" — "Add optimistic toast + rollback on 4xx in `useApprovals`".>

## I — Impact & Priority
- **Priority:** `[ P0 | P1 | P2 | P3 ]`
- **Result:**   `[ 🌊 FLOW | ⚠️ FRICTION | ⛔ BROKEN | 🔲 MISSING ]`

### Frequency × Severity matrix
| Freq ↓ / Sev → | Low | Med | High | Critical |
|----------------|-----|-----|------|----------|
| Always         | P2  | P1  | P0   | P0       |
| Often          | P2  | P1  | P1   | P0       |
| Sometimes      | P3  | P2  | P1   | P1       |
| Rarely         | P3  | P3  | P2   | P2       |

### Mark the cell that applies and justify.
