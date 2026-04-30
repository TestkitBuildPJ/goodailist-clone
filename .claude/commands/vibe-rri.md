---
description: Open RRI Requirements Matrix template + methodology guide
version: 0.11.3
allowed-tools: [Bash, Read]
wired_refs: [ref-21, ref-29]
---

# /vibe-rri — Reverse Requirements Interview

Run an RRI session with the 5 canonical personas (End User, Business
Analyst, QA, Developer, Operator) across CHALLENGE / GUIDED / EXPLORE
modes.  Output: a populated Requirements Matrix, a Decisions Log, and
an empty Open-Questions list.

## Usage

```bash
cat ai-rules/vibecodekit/templates/rri-matrix.md
cat ai-rules/vibecodekit/references/29-rri-reverse-interview.md
```

## When to use
- Starting a new module / screen / feature
- After a SCAN of an existing repo, before proposing VISION
- When a TIP can't be implemented because the spec is ambiguous

## Output
Save to `docs/rri/<feature>-rri.md`.  The matrix feeds the VERIFY step
(requirement traceability) at the end of the module.

## References

- `ai-rules/vibecodekit/references/21-rri-methodology.md`
- `ai-rules/vibecodekit/references/29-rri-reverse-interview.md`

<!-- v0.11.3-runtime-wiring-begin -->
## Runtime wiring (v0.11.3)

Compose the LLM context block for this command from wired references + dynamic data:

```bash
PYTHONPATH=ai-rules/vibecodekit/scripts python -m vibecodekit.cli context \
  --command vibe-rri \
  --project-type <type> --persona <p> --mode <m>
```

**Wired references:** ref-21, ref-29 — loaded verbatim by `methodology.render_command_context`.

**Dynamic data sources:** rri-questions — pulled at runtime per project context.

<!-- v0.11.3-runtime-wiring-end -->
