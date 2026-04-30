# VIBECODE Master — 3-actor, 8-step workflow

VibecodeKit's author-facing pipeline is the **3-actor, 8-step VIBECODE
Master** methodology.  The runtime is the *execution engine* beneath
it; this file describes the **people process** the runtime supports.

## 1. Three actors (quyền lực tam giác)

| Actor                  | Role                                                        | Primary artefact        |
|------------------------|-------------------------------------------------------------|-------------------------|
| **Con người (Homeowner)** | Strategy, approvals, context the AI doesn't have          | Approve / Reject / Adjust |
| **Chủ thầu (Contractor)** | Design, RRI, orchestration — *never* writes application code | Vision, Blueprint, TIPs, Verify |
| **Thợ (Builder)**        | Implements exactly what the TIP specifies — *never* redesigns | Completion report       |

A single Claude Chat or Devin conversation acts as the Contractor; Claude
Code / Devin's shell is the Builder; the human user is the Homeowner.

## 2. Eight steps

```
   1.SCAN  →  2.RRI  →  3.VISION  →  4.BLUEPRINT
                                          │
                                          ▼
   8.REFINE ←  7.VERIFY  ←  6.BUILD  ←  5.TASK GRAPH
```

| #  | Step        | Owner      | Output                                               |
|----|-------------|------------|------------------------------------------------------|
| 1  | SCAN        | Builder    | `scan-report.md` (tech stack, modules, gaps)         |
| 2  | RRI         | Contractor | Requirements matrix, DECISIONS, OPEN QUESTIONS        |
| 3  | VISION      | Contractor | Project type + layout + style + stack proposal       |
| 4  | BLUEPRINT   | Contractor | Full design locked by `APPROVED`                     |
| 5  | TASK GRAPH  | Contractor | Dependency DAG of TIPs, execution order              |
| 6  | BUILD       | Builder    | One PR per TIP + `completion-report.md`              |
| 7  | VERIFY      | Contractor | Requirement traceability + RRI-T + RRI-UX results    |
| 8  | REFINE      | All        | Ship / iterate decision                              |

## 3. Project-type detection (step 3.1)

| Type                 | Keywords                                                 | Default stack suggestion           |
|----------------------|----------------------------------------------------------|------------------------------------|
| Landing page         | bán, giới thiệu, landing, marketing                      | Next.js + Tailwind + Framer        |
| SaaS application     | app, ứng dụng, quản lý, platform                         | Next.js + Supabase + NextAuth      |
| Dashboard            | dashboard, thống kê, báo cáo, analytics, admin           | Next.js + Recharts + Shadcn        |
| Blog / Documentation | blog, bài viết, tài liệu, docs, hướng dẫn                | Next.js + MDX                      |
| Portfolio            | portfolio, cá nhân, agency, showcase                     | Next.js + Tailwind + Framer        |
| Enterprise module    | thêm module, quản lý [X], tích hợp                       | **Keep stack from Scan**           |
| Custom / Hybrid      | unclear                                                   | Ask extra clarifying questions      |

## 4. TIP — Task Instruction Pack

A TIP is the **unit of execution** that Contractor hands to Builder.  It
MUST contain: Header, Context, Task, Specifications, Acceptance criteria
(Gherkin), Constraints, and Report-format pointer.

Template: `assets/templates/tip.md` — `/vibe-tip` opens it.

## 5. Completion report

Builder responds with a `completion-report.md` that contains:

* `STATUS`: `DONE` / `PARTIAL` / `BLOCKED`
* `FILES CHANGED` (created / modified list)
* `TEST RESULTS` (acceptance criteria X / Y passed)
* `ISSUES DISCOVERED` (severity + suggestion)
* `DEVIATIONS FROM SPEC` (what / why / impact)
* `SUGGESTIONS FOR CHỦ THẦU`

Template: `assets/templates/completion-report.md` — `/vibe-complete`.

## 6. Escalation protocol (3 levels)

```
L1  Builder self-resolves       — implementation details, minor opts, std errors
L2  Builder → Contractor decides — spec ambiguity, pattern choice, perf trade-offs
L3  Contractor → Homeowner       — scope change, architecture, budget, compliance
```

## 7. Blueprint is a contract

Once the Homeowner replies `APPROVED` to the Blueprint, it is **frozen**.
Architecture changes require going back to step 3 (VISION).  Small
copy / colour / content-in-existing-section edits can be handled through
`REFINE` without going back to VISION.

## 8. REFINE — canonical envelope (BƯỚC 8/8)

`REFINE` is the eighth and final step of the v5 pipeline.  It exists so
copy / colour / spacing iteration can ship without re-running BƯỚC 3
(VISION).  The envelope is **strict**: any change that crosses the
boundary must loop back to VISION.

**CÓ THỂ refine (in-scope for `/vibe-refine`):**
- Thay đổi text / copy (i18n strings, headlines, button labels)
- Điều chỉnh màu nhỏ (CSS tokens, hover states)
- Thêm/bớt nội dung trong section có sẵn (testimonial, FAQ entry, copy block)
- Fix issues từ Verify Report (typos, accessibility a11y nits)

**KHÔNG THỂ refine (cần quay BƯỚC 3 — VISION):**
- Thêm section / feature / route / component mới
- Đổi layout / structure (DOM order, breakpoints, grid)
- Thay đổi tech stack / dependencies (`package.json`, `requirements.txt`)
- Thêm module / migration / schema mới (`prisma/schema.prisma`,
  `next.config.*`, `tsconfig.json`, `tailwind.config.*`)

`refine_boundary.classify_change(diff)` enforces this list as a
deterministic classifier (returns `in_scope` or `requires_vision`).
Conformance probe `40_refine_boundary_step8` verifies the classifier +
the slash command + the `assets/templates/refine.md` ticket template
remain wired together.

## 9. Verify = RRI in reverse

`VERIFY` walks every REQ-* from the RRI matrix and asks four questions:

1. **Requirement traceability** — implemented / missing / partial?
2. **Scenario walk-through** (End User persona) — happy path, edge cases.
3. **Stress test** (QA persona) — concurrent, invalid input, slow network.
4. **Technical health** (Developer persona) — build, types, lint, coverage.

Template: `assets/templates/verify-report.md` — `/vibe-verify`.

## 10. Integration with the agentic runtime

| VIBECODE step | Runtime feature(s) involved                           |
|---------------|-------------------------------------------------------|
| SCAN          | `task_runtime.start_local_workflow` (read-only steps) |
| RRI           | `memory_hierarchy` (persist decisions across sessions)|
| VISION        | `subagent_runtime` (Architect + Security personas)    |
| BLUEPRINT     | `approval_contract` (kind = `diff`, risk tiering)     |
| TASK GRAPH    | `quality_gate` (7 D × 8 A scorecard per TIP)          |
| BUILD         | `tool_executor` + `permission_engine` + `cost_ledger` |
| VERIFY        | `conformance_audit` + RRI-T test generation           |
| REFINE        | `cost_ledger.summary()` + `denial_store` metrics      |
