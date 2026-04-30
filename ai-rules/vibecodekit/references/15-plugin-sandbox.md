# Pattern #15 — Plugin / hook sandbox

**Source:** `plugins/loadPluginAgents.ts` (Giải phẫu §10.4)

## Rules
1. Plugins **cannot** override `permissionMode`, `hooks`, `mcpServers`
   at agent level — those escalate trust beyond install-time.
2. Remote MCP skills cannot run inline shell commands (Pattern #12).
3. Plugin-level hooks run only with a **filtered environment**.

## v0.7 environment filter
By default any env var whose name matches:

```
(TOKEN|KEY|SECRET|PASSWORD|PASSWD|PRIVATE|CREDENTIAL)
```

is stripped before the hook subprocess is launched.  Override with
`VIBECODE_HOOK_ALLOW_SECRETS=1` only when explicitly needed (and document
why).

## How v0.7 enforces it
- `hook_interceptor._filter_env()` strips secrets.
- Tests `test_hook_env_strips_secrets_by_default`,
  `test_hook_non_executable_auto_chmod`.
- Probe `15_plugin_sandbox` injects a sentinel `GITHUB_TOKEN` and asserts
  it's removed.
