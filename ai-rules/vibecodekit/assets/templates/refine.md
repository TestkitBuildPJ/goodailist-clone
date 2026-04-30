# Refine Ticket — `<short-title>`

> Step 8/8 of the v5 VIBECODE pipeline.  REFINE is **not** a free-form edit
> step: only certain classes of change belong here.  Anything outside this
> envelope must loop back to BƯỚC 3 (VISION) instead.

## 1. Refine ticket

| Field | Value |
|---|---|
| Ticket id | REFINE-`<NNNN>` |
| Originating verify report | `<path or git ref>` |
| Author | `<name>` |
| Mode | `quick` / `targeted` / `verify-driven` |
| Priority | P0 / P1 / P2 |
| Estimated effort (min) | `<int>` |
| Boundary classifier verdict | `in_scope` ✅ / `requires_vision` ⛔ |

### Description
<what is being refined and why>

### Files in scope
- `<path>` — `<one-line reason>`
- ...

### Verify-report items addressed
- VR-`<id>`: `<short summary>` → status after refine: `<DONE / DEFERRED>`
- ...

## 2. Guard-rail checklist (auto-fail if ANY = "yes")

A refine ticket is **rejected** the moment a single answer below becomes
"yes".  Re-run BƯỚC 3 (VISION) instead.

- [ ] Adding a brand-new route, page, or API endpoint?
- [ ] Adding a brand-new top-level React component / screen?
- [ ] Adding/removing a npm/pnpm/yarn package or other dependency?
- [ ] Modifying `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`?
- [ ] Modifying `prisma/schema.prisma`, an Alembic migration, or any
      `*.sql` schema file?
- [ ] Modifying `next.config.*`, `tsconfig.json`, `tailwind.config.*`,
      `Dockerfile`, or `docker-compose.yaml`?
- [ ] Renaming files or directories?
- [ ] Changing the layout/structure of an existing page (replacing a
      `<section>` with new ones, swapping `<header>`/`<footer>`, etc.)?
- [ ] Adding a new module / feature folder under `src/` or `app/`?
- [ ] Touching CI/CD workflows under `.github/workflows/` or
      similar (`.gitlab-ci.yml`, `Makefile`, etc.)?

If ALL answers are "no" you are inside the v5 refine envelope.

## 3. In-scope edits (allowed in REFINE)

- ✅ Text/copy tweaks (Vietnamese-first; respect `12-vn-checklist.md`).
- ✅ Small color / spacing / typography token adjustments
  (CSS variable values; do not introduce new tokens).
- ✅ Add or remove content **inside an existing section** without
  changing the section's contract or layout.
- ✅ Bug fixes that come from a verify report and only touch already-
  existing files (no new exports, no new top-level components).
- ✅ Localized accessibility fixes (alt text, aria labels, contrast).

## 4. Verification after refine

Run the same verify gate as before BƯỚC 7 (VERIFY):

- `vibecodekit refine classify <diff>` returns
  `{"kind": "in_scope"}`.
- All previously failing items in the source verify report now flip to
  `DONE` or `DEFERRED` (no new MISSINGs).
- The release-gate aggregate (`quality_gate.py`) still ≥ 85 %.
- VN checklist remains 12/12.
- 0/12 SaaS anti-pattern violations (see
  `references/32-rri-ux-critique.md` §10).

## 5. Sign-off

| Role | Person | Date | Status |
|---|---|---|---|
| Author | | | |
| Reviewer | | | |
| Verify gate (auto) | quality_gate | | PASS / FAIL |
| Boundary classifier (auto) | refine_boundary | | in_scope / requires_vision |
