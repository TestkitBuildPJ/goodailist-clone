# RRI Requirements Matrix — <title>

> Produced by Contractor during step 2 (RRI).  Homeowner signs off
> before VISION.  See `references/29-rri-reverse-interview.md` and
> the canonical question bank in `assets/rri-question-bank.json`
> (loaded via `methodology.load_rri_questions(project_type, persona=…, mode=…)`).

---

## Project type & question budget
- **Project type:** `[ landing | saas | dashboard | blog | docs | portfolio | ecommerce | enterprise-module | custom ]`
- **Minimum question budget for this type** (from `rri-question-bank.json` `expected_min`):
  - landing 25 · saas 50 · dashboard 35 · blog 25 · docs 30
  - portfolio 25 · ecommerce 40 · enterprise-module 45 · custom 15
- **Personas covered:** `end_user`, `ba`, `qa`, `developer`, `operator` (5/5 must appear).
- **Modes covered:** `CHALLENGE`, `GUIDED`, `EXPLORE` (3/3 must appear; ≥1 question per persona × mode where bank size allows).

## Auto-answered (from SCAN)

| #   | Question                        | Auto answer (evidence)                |
|-----|---------------------------------|---------------------------------------|
| 1   |                                 |                                       |

## Asked questions — by persona × mode

> Pull the canonical IDs from `methodology.load_rri_questions(project_type, persona, mode)`.
> Each row records *which* question was asked and the live answer.

| Q-ID            | Persona     | Mode      | Question (paraphrased)        | Answer       |
|-----------------|-------------|-----------|-------------------------------|--------------|
| S-EU-EX-01      | end_user    | EXPLORE   |                               |              |
| S-BA-CH-01      | ba          | CHALLENGE |                               |              |
| S-QA-GU-01      | qa          | GUIDED    |                               |              |
| S-DV-GU-01      | developer   | GUIDED    |                               |              |
| S-OP-EX-01      | operator    | EXPLORE   |                               |              |

## Requirements — by persona

| REQ-ID  | Requirement                    | Source (Q-ID) | Priority | Persona     |
|---------|--------------------------------|---------------|----------|-------------|
| REQ-001 |                                |               | P0       | end_user    |
| REQ-002 |                                |               | P1       | ba          |
| REQ-003 |                                |               | P0       | qa          |
| REQ-004 |                                |               | P1       | developer   |
| REQ-005 |                                |               | P0       | operator    |

## Mode coverage check (must be all-green before VISION)

| Persona     | CHALLENGE asked | GUIDED asked | EXPLORE asked |
|-------------|:---------------:|:------------:|:-------------:|
| end_user    |        ✓        |       ✓      |       ✓       |
| ba          |        ✓        |       ✓      |       ✓       |
| qa          |        ✓        |       ✓      |       ✓       |
| developer   |        ✓        |       ✓      |       ✓       |
| operator    |        ✓        |       ✓      |       ✓       |

> A cell is allowed to be `—` only if the bank itself does not ship
> that combination (the `custom` project type is the only documented
> exception).  Otherwise: not asked, not signed off.

## Decisions log

| D-ID  | Decision                | Options considered          | Chosen | Rationale |
|-------|-------------------------|-----------------------------|--------|-----------|
| D-001 |                         | A / B / C                   | A      |           |

## Open questions (must be empty before VISION)

| OQ-ID  | Question                               | Owner    | By when    |
|--------|----------------------------------------|----------|------------|
| OQ-001 |                                        |          |            |

## Sign-off
- Contractor: <date>
- Homeowner:  <date, APPROVED / ADJUST>
