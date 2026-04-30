---
description: UI design via combined RRI-UX + RRI-T methodology
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-22, ref-33, ref-34]
deprecated: true
replaced-by: /vibe-rri
removal-target: v1.0.0
deprecation-note: |
  /vibe-rri canonical đã cover UI axis qua mode GUIDED + dùng prompt
  phụ "design pipeline".  Variant riêng /vibe-rri-ui sẽ remove ở
  v1.0.0; giữ hiện tại để backward-compat.
---

# /vibe-rri-ui — UI design combining UX + Testing

Run the four-phase RRI-UI pipeline: **Setup → UX Critique → Component
Design → Testing**, so UX anti-patterns are caught in *design*, not in
*code*, and the design itself is testable by construction.

## Usage

```bash
cat ai-rules/vibecodekit/references/33-rri-ui-design.md
cat ai-rules/vibecodekit/templates/rri-ux-critique.md
cat ai-rules/vibecodekit/templates/rri-t-test-case.md
```

## Phases
1. **Phase 0 (Setup)** — tokens, requirements, constraints
2. **Phase 1 (UX Critique)** — 5 UX personas × 8 flow-physics axes
3. **Phase 2 (Component Design)** — inline 8-point self-check
4. **Phase 3 (Testing)** — 5 testing personas × 7 dimensions × 8 stress axes

## Release gate
- All 7 UX dimensions ≥ 70 % FLOW
- All 7 testing dimensions ≥ 70 % PASS
- At least 5 / 7 of each ≥ 85 %
- 12 / 12 Vietnamese checklist items pass
- 0 P0 items in BROKEN or FAIL

## References

- `ai-rules/vibecodekit/references/22-rri-ux-ui.md`
- `ai-rules/vibecodekit/references/33-rri-ui-design.md`

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-rri-ui
```

**Wired references:** ref-22, ref-33, ref-34 — loaded verbatim by `methodology.render_command_context`.

<!-- v0.11.3-runtime-wiring-end -->
