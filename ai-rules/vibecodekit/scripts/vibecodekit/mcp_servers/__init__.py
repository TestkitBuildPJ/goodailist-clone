"""Bundled in-process MCP servers for the vibecodekit runtime.

Each module in this package is a tiny callable-based "server" usable with
the ``transport: "inproc"`` option of :mod:`vibecodekit.mcp_client`.

A "tool" is just a top-level function whose name is invoked by
``call_tool(...)``.  Return values are wrapped in ``{"ok": True,
"result": <value>}`` by the client.
"""
