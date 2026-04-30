# Pattern #11 — Conditional skill activation

**Source:** `skills/` 4 066 LOC (Giải phẫu §9)

## Rule
A skill's `paths:` frontmatter list is a set of gitignore-style globs.  The
skill activates only when an agent touches a file matching at least one
pattern.

## v0.7 semantics
- Matching is done with `fnmatch` (case-sensitive).
- No `paths` list ⇒ always-on skill.
- The skill's directory must not be inside `.gitignore`'d paths,
  `node_modules`, `.venv`, `venv`, `__pycache__`, `.git`, `.vibecode`,
  `dist`, or `build`.

## How v0.7 enforces it
- `skill_discovery.discover(root, touched=...)`.
- Probe `13_dynamic_skill_discovery` and the tests in
  `tests/test_skill_discovery.py` exercise both happy-path activation and
  `node_modules` shielding.
