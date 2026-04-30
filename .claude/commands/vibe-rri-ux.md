---
description: Open RRI-UX critique template + flow-physics methodology
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-22, ref-32]
deprecated: true
replaced-by: /vibe-rri
removal-target: v1.0.0
deprecation-note: |
  /vibe-rri canonical đã cover UX axis qua mode CHALLENGE.  Variant
  riêng /vibe-rri-ux sẽ remove ở v1.0.0; giữ hiện tại để backward-
  compat session cũ.
---

# /vibe-rri-ux — UX Critique (S→V→P→F→I)

Critique an existing or proposed UI against the 5 UX personas × 7
dimensions × 8 Flow Physics axes.  Runs *before* code, not after.

## Usage

```bash
cat ai-rules/vibecodekit/templates/rri-ux-critique.md
cat ai-rules/vibecodekit/references/32-rri-ux-critique.md
```

## UX Personas
- 🏃 Speed Runner
- 👁️ First-Timer
- 📊 Data Scanner
- 🔄 Multi-Tasker
- 📱 Field Worker (3G, one-handed)

## Output
`docs/rri-ux/<screen>-critique.md` — entries in S→V→P→F→I format.
Each 🔲 MISSING entry must feed back into the RRI matrix as a new REQ-*.

## Release gate
- All 7 UX dimensions ≥ 70 % FLOW
- At least 5 / 7 dimensions ≥ 85 %
- 0 P0 items in BROKEN

## References

- `ai-rules/vibecodekit/references/22-rri-ux-ui.md`
- `ai-rules/vibecodekit/references/32-rri-ux-critique.md`

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-rri-ux
```

**Wired references:** ref-22, ref-32 — loaded verbatim by `methodology.render_command_context`.

<!-- v0.11.3-runtime-wiring-end -->
