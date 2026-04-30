# Module spec — Pattern F

> **Reuse-max / build-min** — every entry in NEW BUILD must justify why
> nothing in REUSE INVENTORY can satisfy the requirement.

## 1. Context

| Field | Value |
|---|---|
| Module name | `<name>` |
| One-line spec | `<spec>` |
| Target codebase | `<repo path>` |
| Probe date | `<YYYY-MM-DD>` |
| Owner | `<name>` |

## 2. REUSE INVENTORY

> *Output of `vibecodekit module probe <target>` filtered down to the
> capabilities the new module will lean on.*

| Capability | Evidence | Reuse plan |
|---|---|---|
| `nextjs` | `package.json: next@15.0.0` | App Router — extend `app/<slug>/` |
| `prisma` | `prisma/schema.prisma` | Extend schema; new `model <Name>` |
| `nextauth` | `package.json: next-auth` | `getServerSession()` for module gates |
| `tailwind` | `tailwind.config.ts` | Reuse palette / typography tokens |
| ... | ... | ... |

**Coverage rule**: every NEW BUILD row must cite ≥ 1 inventory row it
*depends on*; if a row depends on nothing (greenfield), justify in
`risks`.

## 3. NEW BUILD

### 3.1 Files

| Path | Purpose | Depends on |
|---|---|---|
| `app/<slug>/page.tsx` | Module entrypoint UI | `nextjs`, `tailwind` |
| `app/api/<slug>/route.ts` | REST handler | `nextjs`, `nextauth`, `prisma` |
| `prisma/migrations/<ts>_add_<slug>.sql` | Schema delta | `prisma` |
| ... | ... | ... |

### 3.2 Tasks (TIPs)

> Hand-off to `/vibe-tip` — each row becomes one TIP.

| TIP-ID | Title | Files | Effort | Depends on |
|---|---|---|---|---|
| TIP-01 | Add `<Name>` Prisma model | `prisma/schema.prisma` | 30m | — |
| TIP-02 | Module page UI | `app/<slug>/page.tsx` | 1h | TIP-01 |
| TIP-03 | API route + auth gate | `app/api/<slug>/route.ts` | 1h | TIP-01 |
| TIP-04 | Tests | `tests/<slug>.test.ts` | 1h | TIP-02, TIP-03 |

### 3.3 Acceptance criteria

* [ ] Module entrypoint is reachable from existing routing.
* [ ] REUSE INVENTORY ≥ N items cited in PR description.
* [ ] Zero duplicate dependencies introduced.
* [ ] All `requires_vision` boundary changes routed through
  `/vibe-vision` first (no new auth provider, ORM, top-level layout).

## 4. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Prisma migration drift | Review SQL diff; rollback via `prisma migrate resolve --rolled-back`. |
| Missing auth gate | All module routes call `getServerSession()` before handler logic. |
| New dependency creep | PR diff `package.json` shows only additions. |

## 5. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Author | | | |
| Reviewer | | | |
| Release gate | | PASS / BLOCK | |
