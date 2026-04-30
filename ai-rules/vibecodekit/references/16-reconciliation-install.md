# Pattern #16 — Reconciliation-based install

**Source:** `PluginInstallationManager.ts` (Giải phẫu §10.5)

## Rule
The destination is the **desired state**.  The installer computes a diff —
create / overwrite / skip — and emits operations idempotently.  Never
deletes orphans automatically.

## v0.7 states

| State     | Meaning                                                                 |
|-----------|-------------------------------------------------------------------------|
| create    | source exists, destination does not                                     |
| overwrite | both exist, content hashes differ                                       |
| skip      | both exist, content hashes match                                        |
| (orphan)  | destination exists but source does not — **ignored**                    |

## How v0.7 enforces it
- `install_manifest.plan()` returns a list of `Planned(source, destination, action)`.
- `install_manifest.install(dst, dry_run=True)` returns a summary without
  touching the filesystem.
- Tests `test_dry_run_plans_creates_on_empty_destination`,
  `test_second_install_skips_unchanged`.
- Probe `16_reconciliation_install` ensures the plan emits ≥ 1 operation.
