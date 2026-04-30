# Pattern #13 — Dynamic skill discovery

**Source:** `skills/discoverSkillDirs.ts` (Giải phẫu §9.4.2)

## Rule
Walk up from the touched file toward the project root; any ancestor that
contains `.claude/skills/*/SKILL.md` contributes skills.  **Deeper =
higher priority**.

## v0.7 semantics
- `skill_discovery.discover(root, touched=...)` does a single `rglob` under
  the root, rather than a per-file walk.  This is simpler and sufficient for
  monorepos up to a few thousand files.
- Skills whose `paths:` don't match `touched` are silently dropped.
- `__pycache__`, `.git`, `node_modules`, `dist`, `build`, `.venv`, `venv`,
  `.vibecode` are hard-skipped.

## How v0.7 enforces it
- Tests `test_skill_discovery.test_finds_skill_with_frontmatter`,
  `test_skips_node_modules`,
  `test_conditional_activation_by_touched_file`.
- Probe `13_dynamic_skill_discovery`: SKILL.md must declare `paths:`.
