# Pattern #14 — Plugin extension points

**Source:** `plugins/` 31 484 LOC (Giải phẫu §10)

## The four extension points

| Point     | Claude Code                     | v0.7 overlay                          |
|-----------|---------------------------------|---------------------------------------|
| Commands  | markdown slash commands         | `.claude/commands/*.md`               |
| Agents    | custom sub-agent cards          | `.claude/agents/*.md`                 |
| Hooks     | 26 lifecycle events             | `hook_interceptor.SUPPORTED_EVENTS`   |
| Servers   | MCP / LSP servers               | declared in `plugin-manifest.json`    |

## v0.7 supported events

`pre_query`, `post_query`, `pre_tool_use`, `post_tool_use`, `pre_tip`,
`post_completion`, `pre_release`, `pre_release_gate`, `pre_compact`,
`post_compact`, `session_start`, `session_end`.

Each event's hook receives:
- `argv[1]` — the triggering command string (for tool events), else `""`
- `$VIBECODE_HOOK_EVENT` — the event name
- `$VIBECODE_HOOK_COMMAND` — identical to argv[1]
- `$VIBECODE_HOOK_PAYLOAD` — full JSON payload
- filtered environment (see Pattern #15).

## How v0.7 enforces it
- `assets/plugin-manifest.json` declares `commands`, `agents`, `hooks`.
- Probe `14_plugin_extension` checks manifest keys.
- Tests in `tests/test_hook_interceptor.py` verify argv + env + JSON return.
