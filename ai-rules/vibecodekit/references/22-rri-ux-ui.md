# RRI for UX/UI work

Same 5 personas, but the artefacts differ for visual/interaction work.

| Persona          | UX/UI artefact                                                   |
|------------------|------------------------------------------------------------------|
| Architect        | IA map, user journey, success metric (task completion rate, ...)|
| Implementation   | Figma / code diff, storybook, design tokens                      |
| Verifier         | a11y audit (WCAG 2.2 AA baseline), empty/error/offline states    |
| Security Auditor | XSS / clickjacking / open-redirect review of affected screens    |
| Compliance       | brand & legal review (copy, dark-pattern scan, consent UX)       |

## The 7 UX/UI dimensions

1. **Comprehension** — user understands the screen's purpose in ≤ 5 s.
2. **Affordance** — interactive elements look interactive.
3. **Feedback** — every action produces a visible result within 100 ms.
4. **Error resilience** — every possible input is handled; failure modes
   are explicit, not silent.
5. **Accessibility** — WCAG 2.2 AA; keyboard reachable; screen-reader
   compatible; colour contrast ≥ 4.5:1.
6. **Performance** — LCP < 2.5 s on 3G, JS budget ≤ 170 KB gzip.
7. **Consent & privacy** — no dark patterns; cookie prompts explicit.

## The 8 UX/UI axes (SVPFI-aligned)

1. Intent fit (does the UI match the user's goal?)
2. Scope fit (are we adding unrelated features?)
3. Edge cases (empty / error / offline / slow-network)
4. Fail modes (what does "broken" look like?)
5. Rollback (can we revert without data loss?)
6. Privacy (what personal data is newly surfaced?)
7. Accessibility (WCAG baseline met)
8. Cost (JS / image budget, perceived latency)
