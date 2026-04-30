# Pattern #17 — Pure-TS native module replacement (policy only)

**Source:** `native-ts/yoga-layout/` 2 578 LOC (Giải phẫu §11)

## Principle
Claude Code avoids shipping compiled native modules (C/C++/Rust binaries)
because they complicate distribution, increase supply-chain risk, and slow
agent bootstrap.  The Yoga flexbox layout engine was ported from C to pure
TypeScript for this reason.

## v0.7 policy
- The overlay is **pure Python 3.9+** with stdlib-only dependencies
  (pytest is a dev-dep only).
- No `C` extensions, no `cffi`, no compiled bindings.
- If a feature genuinely needs a native module (rare for an overlay of
  this kind), we document it in the README and mark it optional.

## How v0.7 enforces it
- `setup.py` / `pyproject.toml` declare zero runtime dependencies.
- Probe `17_pure_ts_native_replacement` just checks this reference exists.
