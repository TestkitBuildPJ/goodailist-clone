# Blueprint — <title>

> Fill every section.  Empty sections block the release gate.

## 1. Problem statement (≤ 200 words)
<What user pain triggered this work? Cite the ticket / conversation.>

## 2. Scope
- **In scope:** <files / modules / endpoints touched>
- **Out of scope:** <explicit exclusions>

## 3. Success metrics
| Metric              | Current       | Target       | How measured         |
|---------------------|---------------|--------------|----------------------|
| <e.g. p95 latency>  | <baseline>    | <target>     | <Prom query / test>  |

## 4. Entities & data flows
<ASCII / Mermaid diagram; name every node.>

## 4a. RRI Requirements matrix

> Every `REQ-*` from the RRI session must surface here, paired with the
> blueprint section that addresses it.  Verify report (BƯỚC 7) reuses
> this matrix to compute coverage.

| REQ-ID  | Requirement (one-line)            | Blueprint section | Source (RRI Q#) | Acceptance criteria               |
|---------|-----------------------------------|-------------------|-----------------|-----------------------------------|
| REQ-001 | <e.g. "User can log in via OTP">  | §4 Data flows / §6 Risks | RRI-Q3 | <measurable / observable signal>  |
| REQ-002 |                                   |                   |                 |                                   |
| REQ-003 |                                   |                   |                 |                                   |

## 4b. Task decomposition preview

> Pre-decompose Build (BƯỚC 6) into TIPs **before** writing code so the
> verify gate has a stable target.

```
Estimated tasks: <N>
Estimated effort: <minutes> min total

├── TIP-001: <short title>                                (~<min> min)
├── TIP-002: <short title>                                (~<min> min)
├── TIP-003: <short title>                                (~<min> min)
└── TIP-NNN: ...                                          (~<min> min)
```

| TIP-ID  | Title                          | REQ covered  | Effort (min) | Owner |
|---------|--------------------------------|--------------|--------------|-------|
| TIP-001 |                                | REQ-001, ... | <int>        |       |
| TIP-002 |                                |              |              |       |

## 5. Invariants (must always hold)
1. <e.g. "Every mutation logs an audit entry.">
2. <...>

## 6. Risks & mitigations
| Risk                    | Likelihood | Impact | Mitigation                    |
|-------------------------|:----------:|:------:|-------------------------------|
|                         |            |        |                               |

## 7. Decision log
| Date | Decision | Rationale | Alternatives rejected |
|------|----------|-----------|----------------------|
|      |          |           |                      |

## 8. Rollback plan
<Exactly how do we revert? git revert, feature flag, DB migration undo?>

## 9. Sign-off
- Architect: <name + date>
- Implementation Lead: <name + date>
- Security Auditor: <name + date>
- Compliance Steward: <name + date>
