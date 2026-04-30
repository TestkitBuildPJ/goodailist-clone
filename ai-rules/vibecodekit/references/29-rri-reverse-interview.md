# RRI — Reverse Requirements Interview (canonical definition)

VibecodeKit uses **RRI** to mean **Reverse Requirements Interview** —
the methodology described in the RRI, RRI-T, RRI-UX and RRI-UI documents
(© 2025, Vietnamese Enterprise Software).  This file is the authoritative
definition inside the skill bundle.

> **Not to be confused with the v0.7 "Role-Responsibility-Interface"
> 5-persona runtime governance model** documented in `21-rri-methodology.md`.
> That model remains — it governs *who is allowed to do what* inside the
> runtime — but it is an internal runtime concept, not the author-facing
> discovery methodology described here.

## 1. Triết lý (Philosophy)

> "Thay vì hỏi *'Bạn muốn gì?'*, hãy nghĩ *'Nếu tôi là user, tôi cần gì?'*
>  và đề xuất trước, điều chỉnh sau."

RRI is **empathy-first**: the Contractor proposes a concrete vision and
asks the Homeowner to *confirm / adjust / reject*, rather than asking
the Homeowner to describe everything from scratch.

## 2. Five personas (authoritative)

| # | Persona            | Focus                                              |
|---|--------------------|----------------------------------------------------|
| 1 | End User           | UX, workflow, accessibility, mobile, frustrations  |
| 2 | Business Analyst   | Business rules, compliance, reporting, ROI        |
| 3 | QA / Tester        | Validation, error handling, stress, limits        |
| 4 | Developer          | Patterns, technical debt, performance (Scan-based)|
| 5 | Operator / DevOps  | Deploy, monitoring, backup, DR, scaling           |

## 3. Three question modes

* **CHALLENGE mode**  — "I propose X.  Approve / Reject / Adjust."
* **GUIDED mode**    — "Choose one of these: A / B / C (or describe)."
* **EXPLORE mode**   — "Describe a typical day of a user of this module."

## 4. Five-phase workflow

```
SCAN → RRI → VISION → BLUEPRINT → TASK GRAPH → BUILD → VERIFY → REFINE
```

Each phase has a mandatory artefact; see `30-vibecode-master.md` for
the full 8-step pipeline.

## 5. Output format — Requirements matrix

```
| REQ-ID  | Requirement | Source (RRI Q#) | Priority | Persona     |
|---------|-------------|-----------------|----------|-------------|
| REQ-001 | …           | Q#12            | P0       | End User    |
```

Plus a **DECISIONS LOG** (`D-001`, options considered, rationale) and an
**OPEN QUESTIONS** list (`OQ-001`).

## 6. When RRI is complete

* Every Blueprint section has at least one `REQ-*` backing it
  (traceability column is filled).
* Every auto-answered question has an explicit line in the
  "AUTO-ANSWERED" section citing the Scan evidence.
* The `OPEN QUESTIONS` list is empty *or* each entry has a decision
  owner and a by-when.

## 7. Continuous RRI

RRI is a **mindset**, not a one-off phase:

* **Pre-build**  — discover requirements.
* **During-build** — surface gaps when a TIP cannot be implemented as
  specified (BUILDER must report, not invent).
* **Post-build** — the `VERIFY` step is literally *RRI in reverse*:
  take every REQ-* and ask "is this behaviour observable in the built
  system?"  Missing → `MISSING`, not `FAIL`.
