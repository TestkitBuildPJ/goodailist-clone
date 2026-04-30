# RRI-UI — UI Design combining RRI-UX + RRI-T

RRI-UI is the **complete** UI methodology: 5 UX Personas × 7 UX
Dimensions × 8 Flow Physics axes  **plus**  5 Testing Personas × 7
Testing Dimensions × 8 Stress axes — run as a **four-phase pipeline**
*before and during* design, not only after code.

## 1. Phase 0 — Setup (1 day)

* Collect RRI output (requirements), existing wireframes, business
  rules, user roles, Vietnamese-specific constraints.
* Lock **design tokens**: colour palette, typography, spacing scale,
  radius, shadow, motion.

## 2. Phase 1 — UX CRITIQUE BEFORE DESIGN (2-3 days)

Run 5 UX Persona interviews (Speed Runner, First-Timer, Data Scanner,
Multi-Tasker, Field Worker) across 8 Flow Physics axes.

Deliverables:

* **UX Issues list** — 80-120 issues in `S→V→P→F→I` format
* **Flow Map** — routes + entry / exit points
* **Viewport Map** — what's in first viewport for each screen
* **Anti-pattern checklist** — 12 common SaaS anti-patterns

## 3. Phase 2 — COMPONENT DESIGN (3-5 days)

Five **mandatory rules** for every screen:

1. **Forward flow** — next step always RIGHT or BELOW; never force
   the user to scroll back.
2. **CTA always visible** — sticky or floating if content > 1 vp.
3. **Progressive disclosure** — form > 7 fields → wizard / accordion;
   dropdown > 15 items → needs search.
4. **Immediate feedback** — visible response < 100 ms; spinner after
   300 ms; toast on success.
5. **Vietnamese-first** — layout test with longest VN phrase, VND
   dot-thousands, `DD/MM/YYYY` dates.

**Inline self-check** (8 axes) runs as the designer is drawing:
SCROLL / CLICK-DEPTH / EYE-TRAVEL / DECISION-LOAD / RETURN-PATH /
VIEWPORT / VN-TEXT / FEEDBACK.

## 4. Phase 3 — TESTING THE DESIGN (2-3 days)

Use the RRI-T 5 personas × 7 dimensions to stress-test the **design
mockup** (not the code).  Typical stress combinations for UI:

* `DATA × TIME` — 500-row table filtered under 2 s
* `COLLAB × CONCURRENCY` — two tabs, same record, detect + warn
* `SECURITY × LOCALIZATION` — XSS via Vietnamese input
* `INFRASTRUCTURE × FIELD` — offline queue + 3G sync

## 5. Phase 4 — Measurement & Release Gate (1 day)

```
✅ All 7 UX dimensions ≥ 70 %
✅ At least 5/7 UX dimensions ≥ 85 %
✅ 0 items P0 in BROKEN or FAIL
✅ Vietnamese checklist: 12/12 pass
✅ Responsive: 375 / 768 / 1440 px verified
✅ Anti-pattern checklist: 0/12 violations
→ 🟢 UI DESIGN APPROVED — go to code
```

## 6. Prompt templates

See `/vibe-rri-ui` for three prompts:

* **Prompt 1** — UX Critique (Phase 1)
* **Prompt 2** — UI Testing (Phase 3)
* **Prompt 3** — Inline self-check while coding a component

## 7. Coverage matrix

Per module, score each of the 7 UX dimensions by `(FLOW / total) × 100 %`.
Target ≥ 85 % for release.

## 8. Why both RRI-UX and RRI-T?

| Methodology | Runs when | Catches                                        |
|-------------|-----------|------------------------------------------------|
| RRI-UX      | Before code | UX anti-patterns, flow physics violations    |
| RRI-T       | After code  | Spec violations, edge cases, security holes  |
| **RRI-UI**  | Both       | Combines both — design is *testable by construction* |

A module that passes RRI-UX but fails RRI-T is **correct but painful**;
a module that passes RRI-T but fails RRI-UX is **broken for humans**.
Only passing **both** is "Agentic-OS grade".
