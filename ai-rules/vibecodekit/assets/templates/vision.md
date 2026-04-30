# Vision — <title>

> Contractor's proposal, before Blueprint.  Homeowner replies
> `APPROVED` / `ADJUST: <notes>` / `REJECT`.  See
> `references/30-vibecode-master.md` §3.

---

## Project type
`[ Landing | SaaS | Dashboard | Blog | Docs | Portfolio | E-commerce | Mobile | API | Enterprise-module | Custom ]`
(If unclear, list the two most likely and explain trade-offs.)

## Proposed stack

> **Pre-fill from `methodology.PROJECT_STACK_RECOMMENDATIONS` (mirrors
> master v5 Phụ Lục A + ref-34 §1).**  Pick the row that matches
> Project Type above; delete the others; adjust only when the Homeowner
> has an explicit constraint.  For `Custom`, every cell must be filled
> in by hand — no defaults.

| Project type      | Framework                              | Styling                  | State / data                  | Auth                          | Hosting                                 | Notable extras                                |
|-------------------|----------------------------------------|--------------------------|-------------------------------|-------------------------------|------------------------------------------|-----------------------------------------------|
| Landing           | Next.js (App Router)                   | Tailwind                 | —                             | —                             | Vercel                                   | Framer Motion, Resend                         |
| SaaS              | Next.js (App Router)                   | Tailwind + shadcn/ui     | Supabase / Postgres           | NextAuth / Clerk              | Vercel                                   | Prisma, Stripe, Sentry                        |
| Dashboard         | Next.js (App Router)                   | Tailwind + shadcn/ui     | TanStack Query + Postgres     | NextAuth                      | Vercel                                   | Recharts, Redis cache                         |
| Blog              | Next.js (App Router)                   | Tailwind + Typography    | MDX or Sanity                 | —                             | Vercel                                   | rehype-pretty-code, RSS, OG image route       |
| Docs              | Next.js + Nextra                       | Tailwind                 | MDX                           | —                             | Vercel                                   | Algolia DocSearch, i18n vi/en                 |
| Portfolio         | Next.js (App Router)                   | Tailwind                 | MDX                           | —                             | Vercel                                   | Framer Motion, next/image                     |
| E-commerce        | Next.js (App Router)                   | Tailwind + shadcn/ui     | Supabase / Postgres           | NextAuth                      | Vercel                                   | Stripe + VNPay/MoMo, Algolia                  |
| Mobile            | Expo (React Native)                    | NativeWind               | TanStack Query + Supabase     | Supabase Auth / Clerk         | EAS Build + EAS Submit                   | Expo Router, OneSignal push                   |
| API               | FastAPI (Python) / Hono (TypeScript)   | —                        | Postgres + SQLAlchemy/Drizzle | JWT + OAuth2                  | Fly.io / Railway / CF Workers            | pydantic v2, Alembic, OpenAPI auto-docs       |
| Enterprise-module | **Reuse from Scan**                    | Reuse from Scan          | Reuse from Scan               | Reuse                         | Reuse                                    | NEW capability only — Pattern F               |
| Custom            | _Choose explicitly with Homeowner_     | _Choose explicitly_      | _Choose explicitly_           | _Choose explicitly_           | _Choose explicitly_                      | _Spell out every cell — no defaults_          |

## Style direction (canonical IDs from `references/34-style-tokens.md`)

- **Font pairing:** `FP-01 Modern Tech (Plus Jakarta Sans + Inter)` — pick one of `FP-01..FP-06`
- **Primary color:** `CP-01 Trust (#2563EB)` — pick one of `CP-01..CP-06`
- **Accent color:** `CP-02 Energy (#F97316)` — pick from a different row than primary
- **Mood:** `<modern / editorial / playful / enterprise / luxury>`
- **VN typography rules:** see `references/34-style-tokens.md §3`

## Copy direction (canonical IDs from `references/36-copy-patterns.md`)

- **Headline pattern:** `CF-01..CF-03`
- **Primary CTA:** `CF-04` — ≤ 4 words EN, ≤ 6 words VN
- **Pricing copy:** `CF-07` — VND format, `xx.xxx ₫`
- **Empty-state copy:** `CF-08` — verb + outcome, never "No data"
- **Error-state copy:** `CF-09` — what happened + what to do, never "Lỗi"

## Layout sketch
```
┌─────────────────────────────────────┐
│  Header  (auth / search / cta)      │
├─────────────────────────────────────┤
│  Left nav    │    Main content      │
│              │                      │
│              │                      │
└─────────────────────────────────────┘
```

## Information architecture
- Route map (depth ≤ 3 clicks to any page)
- Sitemap
- Core user journeys (Speed Runner, First-Timer)

## Non-negotiables
- <constraint from RRI matrix>
- <constraint from business>

## Open items for Homeowner
1. <question with two concrete options>
2. <question with two concrete options>

## Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|:----------:|------------|
|      |            |            |
