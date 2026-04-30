# 27 — MCP client adapter (Giải phẫu §2.8, Ch 10)

The **Model Context Protocol** (MCP) is the spec Claude Code uses to
connect third-party servers — databases, filesystems, knowledge bases,
APIs — as *additional tool providers*, not hard dependencies.

## v0.8 implementation

Module: `scripts/vibecodekit/mcp_client.py`.

### Manifest

`.vibecode/runtime/mcp-servers.json`:

```json
{
  "servers": [
    {
      "name": "local-fs",
      "transport": "stdio",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "enabled": true
    },
    {
      "name": "vendored-math",
      "transport": "inproc",
      "module": "base64",
      "enabled": true
    }
  ]
}
```

### Transports

**`stdio`** — spawns the server via `subprocess.Popen`, speaks minimal
JSON-RPC (`tools/call`).  Suitable for any MCP-compliant binary.

**`inproc`** — imports a Python module and calls the given function by
name with the provided kwargs.  Enables unit testing of the adapter
without external servers, and lets local Python packages publish MCP
tools without implementing the full wire protocol.

### API

```python
register_server(root, name, *, transport, command=None, module=None,
                env=None, description="") → server dict
list_servers(root) → List[dict]
disable_server(root, name) → bool
call_tool(root, server_name, tool, args=None, timeout=10) → dict
```

### CLI

```bash
vibe mcp --root . register local-fs --transport stdio \
         --command npx -y @modelcontextprotocol/server-filesystem /tmp
vibe mcp --root . list
vibe mcp --root . call local-fs read_file --args-json '{"path": "a.txt"}'
vibe mcp --root . disable local-fs
```

### Audit

Probe `20_mcp_adapter` registers a `base64` in-process server and calls
`b64encode({"s": b"vc"})`, asserting the result is `b"dmM="`.
