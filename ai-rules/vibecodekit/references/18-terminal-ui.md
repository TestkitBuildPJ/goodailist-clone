# Pattern #18 — Terminal-as-browser rendering (policy only)

**Source:** `ink/` 19 865 LOC (Giải phẫu §11)

## Principle
Claude Code forked Ink (React-in-terminal) and extended it with a custom
reconciler so the TUI can render complex, stateful UIs.  Terminals are
treated as small constrained browsers.

## v0.7 policy
- The overlay's CLI is **JSON-first**, not ANSI-art.
- `dashboard.summarise()` returns a dict; the default rendering is plain
  text (easy to pipe); `--json` emits structured output.
- Downstream integrations are free to build their own TUI / web dashboards
  against the event bus (`.vibecode/runtime/*.events.jsonl`).

## How v0.7 enforces it
- All CLI subcommands accept `--json` where it makes sense.
- Probe `18_terminal_ui_as_browser` checks this reference exists.
