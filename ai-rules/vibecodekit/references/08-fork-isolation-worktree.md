# Pattern #8 — Fork isolation via Git worktree

**Source:** `forkSubagent.ts:60-71` (Giải phẫu §6.4)

## Rule
When two sub-agents need to mutate the same repository **in parallel**, each
gets its own Git worktree.  Worktrees share the same object store but have
independent working directories and branches, so they can't stomp on each
other's files.

## v0.7 surface
```bash
python -m vibecodekit.cli subagent spawn builder "implement auth"
# then later:
python -c "from vibecodekit import worktree_executor as w; \
           print(w.create('.', 'auth-fix'))"
# → {"worktree": ".vibecode/runtime/worktrees/auth-fix-<ts>", "branch": "vibe/auth-fix-<ts>"}
```

Worktrees live under `.vibecode/runtime/worktrees/` and are removed
explicitly — never with `--force`.

## Safety notes
- v0.7 never uses `git worktree remove --force` or `git worktree prune`.
- If the directory already has uncommitted work, create() will fail (good;
  we surface the git error rather than overwriting).
- Anti-recursion guard: we refuse to create a worktree *inside* an existing
  worktree (checked by resolving `.git/worktrees/*` entries).

## How v0.7 enforces it
- `worktree_executor.create()`, `remove()`, `list_worktrees()`.
- Probe `08_fork_isolation_worktree`: in a fresh git repo, create must
  succeed with returncode 0.
