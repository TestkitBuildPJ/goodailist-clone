# RRI methodology — 5 personas & SVPFI signals

**RRI** = "Role-Responsibility-Interface".  Every change in a Vibecode
project is owned by **one** of five personas, and the handoff between
personas produces a structured **SVPFI** packet.

## The 5 personas

| Persona              | Primary artefact             | Prohibitions                       |
|----------------------|------------------------------|------------------------------------|
| Project Architect    | Blueprint, RISKS, DECISIONS  | Does not write application code.    |
| Implementation Lead  | TIP, plan.json               | Cannot merge without QA sign-off.   |
| Verifier (QA)        | verify-report.md             | Cannot modify application code.     |
| Security Auditor     | security-note.md             | Cannot grant bypass without Lead.   |
| Compliance Steward   | release-gate.json            | Cannot execute; only gates.         |

## SVPFI — handoff envelope

| Field        | Meaning                                                                    |
|--------------|----------------------------------------------------------------------------|
| **S**cope    | Files / modules / endpoints affected.  A single string, not a list.        |
| **V**erification | What has already been verified; what remains.  Link to verify-report.  |
| **P**rinciples   | Invariants that must hold throughout the change (e.g. "no PII in logs"). |
| **F**ailure modes| Known failure scenarios, their severity, detection path.                |
| **I**nterfaces   | The public contract touched: signature, wire protocol, schema.          |

Every handoff produces one SVPFI packet; it is attached to the TIP and the
completion report.  If any field is missing, the compliance gate refuses
the release.

## Authoring guide
- `S` must be ≤ 280 chars.  If you can't compress it, the TIP is too wide.
- `V` must explicitly cite **at least one adversarial test** (Verifier's
  principle — "try to break it, don't confirm it").
- `P` must reference at least one principle from `.vibecode/principles.md`
  or the Blueprint.
- `F` must list **at least three** failure modes (happy-path-only → fail).
- `I` must describe the *new* contract, not the diff; if the interface is
  unchanged, write "NO-CHANGE".
