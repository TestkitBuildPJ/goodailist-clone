# 35 · Enterprise Module pattern (v5 Pattern F)

> Pattern F of the v5 master spec covers the **most common enterprise
> scenario**: the developer already has a working codebase and wants
> to add a feature module without rebuilding from scratch.

## 1. Golden rule — reuse-max / build-min

Every line of new code must be **justified** against an inventory of
what the existing codebase already provides.  The module workflow
forces this in three stages:

1. **Probe** — `module_workflow.probe_existing_codebase()` enumerates
   detectable capabilities (Next.js / React / Vite / Prisma / NextAuth
   / Tailwind / Express / FastAPI / Django / TypeScript).
2. **Inventory** — `generate_reuse_inventory()` emits a canonical
   reuse hint per capability.
3. **Plan** — `generate_module_plan()` produces a structured plan
   (reuse list + new files + acceptance criteria + risks).

## 2. Refusal contract — empty target ⇒ `EmptyCodebaseError`

If the target directory has no project marker (`package.json`,
`pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`,
`pom.xml`, `build.gradle`), the planner **refuses** with
`EmptyCodebaseError`.  Pattern F requires an existing codebase — empty
targets must go through `/vibe-scaffold` (Pattern A/B/C/D/E) first.

## 3. Stack-aware new-file conventions

| Stack | Module slug → new files |
|-------|--------------------------|
| Next.js | `app/<slug>/page.tsx`, `app/<slug>/layout.tsx`, `app/api/<slug>/route.ts` |
| FastAPI | `api/<slug>/__init__.py`, `api/<slug>/router.py`, `api/<slug>/schemas.py` |
| Express | `api/<slug>/index.ts`, `api/<slug>/routes.ts` |
| Django | `<slug>/models.py`, `<slug>/views.py`, `<slug>/urls.py` |
| Generic | `src/<slug>/index.ts` (or `./<slug>/index.ts` if no `src/`) |

Prisma migrations are added under `prisma/migrations/<ts>_add_<slug>.sql`
when Prisma is detected.

## 4. Risks the planner auto-flags

* **Auth bypass** when NextAuth is detected: every module route must
  call `getServerSession()` before handler logic.
* **Migration rollback complexity** when Prisma is detected: rolling
  back requires manual `prisma migrate resolve --rolled-back`.
* **Missing styling strategy** when Tailwind is *not* detected but
  module produces `.tsx` files: the team must reuse the existing CSS
  strategy (CSS modules / styled-components / plain CSS).

## 5. Acceptance criteria (default)

The planner emits these acceptance criteria by default; the user can
extend them in the module-spec template (`assets/templates/module-spec.md`):

* [ ] Module entrypoint is reachable from existing routing.
* [ ] Reuse inventory ≥ N items cited in PR description.
* [ ] Zero duplicate dependencies introduced.
* [ ] All `requires_vision` boundary changes routed through
  `/vibe-vision` first.

## 6. Workflow integration

```text
/vibe-module probe ./repo            ──►  CodebaseProbe (JSON)
/vibe-module plan --name … --spec …  ──►  ModulePlan (JSON)
                              │
                              ▼
                       module-spec.md
                              │
                              ▼
                  /vibe-blueprint (BƯỚC 4)
                              │
                              ▼
                  /vibe-tip → BUILD → VERIFY → REFINE
```

The plan JSON is intentionally tiny and fully serialisable so it can
hop slash-command boundaries without re-running the probe.
