# Pattern #12 — Shell-in-prompt (policy only)

**Source:** `skills/executeShell.ts` (Giải phẫu §9.5)

## Policy decision for v0.7
We **do not** execute shell commands embedded in skill prompts.  Claude
Code does, but gates it heavily (MCP skills are banned from inline shell
for RCE reasons).  v0.7 users who want dynamic context should explicitly
add a `run_command` step to their plan instead of relying on skill-prompt
magic.

## Why
- Shell-in-prompt crosses the tool boundary in a way that the permission
  pipeline can't easily analyse (it looks like data, not a tool call).
- Expanding it also bypasses the user's `allowed-tools:` restriction.
- Our hosts (Devin, Cursor, local scripts) already have a first-class
  shell tool — there is no need for a second one.

## Escape hatch
A future release can add `!cmd` expansion under an explicit
`--dangerous-shell-in-prompt` flag.  Until then: write a TIP step that
runs the command as a normal tool use.

## How v0.7 enforces it
- This reference's existence is the audit signal (probe `12_shell_in_prompt`).
- No code path in `tool_executor` evaluates backtick substitution in skill
  bodies.
