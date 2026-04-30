# 28 — Cost / telemetry ledger (Giải phẫu §12.4)

Giải phẫu §12.4 describes telemetry as **the sensory system** of an
Agentic OS: you cannot operate what you cannot observe.  The ledger is
the append-only record of tokens, tool calls, and cost that turns the
agent loop into a measurable system.

## v0.8 implementation

Module: `scripts/vibecodekit/cost_ledger.py`.

### Files

```
.vibecode/runtime/ledger.jsonl          # append-only event log
.vibecode/runtime/ledger-summary.json   # rolled-up totals (rewritten on summary())
```

Writes are POSIX-atomic line-appends; no lock required for payloads
< 4 KB (PIPE_BUF).

### Events

`kind == "turn"`:

```json
{"kind":"turn","turn_no":1,"model":"sonnet",
 "prompt_tokens":123,"completion_tokens":45,"total_tokens":168}
```

`kind == "tool"`:

```json
{"kind":"tool","tool":"read_file","latency_ms":1.8,
 "bytes_in":40,"bytes_out":1200,"status":"ok"}
```

Callers can also use `record_event(root, arbitrary_dict)` for custom
events (recovery, hook-denial, MCP call, etc.).

### Cost table

```python
COST_TABLE = {
    "default": {"input": 3.0,  "output": 15.0, "cached": 0.30},
    "sonnet":  {"input": 3.0,  "output": 15.0, "cached": 0.30},
    "haiku":   {"input": 1.0,  "output":  5.0, "cached": 0.10},
    "opus":    {"input": 15.0, "output": 75.0, "cached": 1.50},
}
```

Numbers are per-million-tokens-USD, illustrative defaults.

### Integration with the query loop

`query_loop.run_plan()` automatically records a `turn` event per turn
and a `tool` event per executed block.  At the end of the plan, a
`cost_summary` event is emitted and a `cost` key is attached to the
return value.

### CLI

```bash
vibe ledger --root . summary
vibe ledger --root . reset
```

### Audit

Probe `21_cost_accounting_ledger` records a single turn and tool call,
then asserts `s["turns"] == 1 and s["tool_calls"] == 1 and
s["cost_usd"] > 0`.
