---
description: Open RRI-T (testing) template + 5×7×8 methodology
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-31]
deprecated: true
replaced-by: /vibe-rri
removal-target: v1.0.0
deprecation-note: |
  /vibe-rri canonical đã cover testing axis qua mode CHALLENGE/GUIDED
  /EXPLORE.  Variant riêng /vibe-rri-t sẽ remove ở v1.0.0; giữ
  hiện tại để backward-compat session cũ invoke.
---

# /vibe-rri-t — RRI for Testing (Q→A→R→P→T)

Run a test-discovery session across 5 Testing Personas × 7 Dimensions ×
8 Stress Axes.  Goal: surface every edge case the RRI didn't.

## Usage

```bash
cat ai-rules/vibecodekit/templates/rri-t-test-case.md
cat ai-rules/vibecodekit/references/31-rri-t-testing.md
```

## Personas
- 👤 End User Tester
- 📋 Business Analyst
- 🔍 QA Destroyer
- 🛠️ DevOps Tester
- 🔒 Security Auditor

## Output
`docs/rri-t/<module>-tests.md` — one entry per test.  Each entry scores
a Dimension (D1-D7) and stress axes (1-3).  Run all P0 tests before
release; coverage matrix is part of the verify report.

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-rri-t
```

**Wired references:** ref-31 — loaded verbatim by `methodology.render_command_context`.

<!-- v0.11.3-runtime-wiring-end -->
