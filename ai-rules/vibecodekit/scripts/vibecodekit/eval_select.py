"""eval_select — diff-based test selection (a.k.a. touchfiles).

A tiny, dependency-free re-implementation of the "run only tests that
touch files in the diff" pattern popularised by gstack's eval pipeline.
We intentionally keep it simple enough to explain in a code-review:

  1. ``git diff --name-only <base>`` gives the changed files.
  2. A ``TOUCHFILES_MAP`` (JSON or Python) maps each test to the set of
     source files it covers.  Tests with no entry are conservatively
     treated as "always run".
  3. ``select_tests(changed_files, touchfiles_map)`` returns the subset
     of tests that (a) cover a changed file, or (b) are marked
     ``always_run``.

Conservative by design: missing or empty touchfile entries fall back to
"always run" so a stale map can never cause a test to be silently
skipped.

CLI:
    python -m vibecodekit.eval_select --base origin/main --map tests/touchfiles.json
"""

from __future__ import annotations

import fnmatch
import json
import os
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "TouchfileMap",
    "load_map",
    "git_changed_files",
    "select_tests",
    "SelectionResult",
]


@dataclass(frozen=True)
class SelectionResult:
    """Tests selected for execution, plus the explanation."""

    selected: Sequence[str]
    always_run: Sequence[str]
    matched: dict[str, Sequence[str]]  # test -> list of matching changed files
    unmapped_changes: Sequence[str]

    def as_dict(self) -> dict:
        return {
            "selected": list(self.selected),
            "always_run": list(self.always_run),
            "matched": {k: list(v) for k, v in self.matched.items()},
            "unmapped_changes": list(self.unmapped_changes),
        }


TouchfileMap = dict[str, Sequence[str]]


def load_map(path: Path | str) -> TouchfileMap:
    """Load a touchfiles map from JSON.

    Accepted shapes::

        { "tests/foo.py": ["src/foo.py", "src/foo/*.py"] }

        { "tests/foo.py": { "files": [...], "always_run": true } }

    ``always_run: true`` adds the test to the always-run list regardless
    of the diff.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"touchfile map not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"touchfile map must be a JSON object, got {type(raw).__name__}")
    out: dict[str, list] = {}
    for test, value in raw.items():
        if isinstance(value, list):
            out[test] = list(value)
        elif isinstance(value, dict):
            files = list(value.get("files", []))
            if value.get("always_run"):
                files.append("__ALWAYS__")
            out[test] = files
        else:
            raise ValueError(f"bad touchfile entry for {test!r}: {value!r}")
    return out


def git_changed_files(base: str = "origin/main", cwd: Path | None = None) -> list[str]:
    """Return files changed vs ``base`` (``git diff --name-only --merge-base``).

    Falls back to an empty list if git is unavailable — the caller can
    then decide to run the full suite.
    """
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"--merge-base={base}"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def _match(pattern: str, path: str) -> bool:
    # Exact match; glob match; directory prefix match.
    if pattern == path:
        return True
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.endswith("/") and path.startswith(pattern):
        return True
    return False


def _normalise_entry(value) -> list:
    """Accept the two load_map shapes inline so callers can pass raw JSON.

    An empty patterns list (``[]`` or ``{"files": []}`` without
    ``always_run``) is conservatively promoted to always-run — see the
    module docstring's contract: "missing or empty touchfile entries
    fall back to 'always run' so a stale map can never cause a test to
    be silently skipped."
    """
    if isinstance(value, list):
        out = list(value)
        if not out:
            out = ["__ALWAYS__"]
        return out
    if isinstance(value, dict):
        out = list(value.get("files", []))
        if value.get("always_run") or not out:
            # Empty ``files`` without an explicit ``always_run: false``
            # is treated as always-run.  Operators who want a test to
            # never run on diff-changes can simply drop the entry.
            if "__ALWAYS__" not in out:
                out.append("__ALWAYS__")
        return out
    raise ValueError(f"bad touchfile entry: {value!r}")


def select_tests(
    changed_files: Iterable[str],
    touchfiles: TouchfileMap,
    extra_always_run: Sequence[str] = (),
    fallback_all_tests: Iterable[str] | None = None,
) -> SelectionResult:
    """Core selection algorithm.

    Parameters
    ----------
    changed_files
        Files changed in the working tree vs the base branch.
    touchfiles
        Map produced by :func:`load_map`.
    extra_always_run
        Tests that must run regardless of the diff (e.g. flaky or
        cross-cutting tests).
    fallback_all_tests
        If given and ``changed_files`` is empty (e.g. a release branch
        with no diff), every test in this iterable is selected.
    """
    changed: list[str] = list(changed_files)
    always: set[str] = set(extra_always_run)
    matched: dict[str, list[str]] = {}
    unmapped: set[str] = set()

    normalised: dict[str, list] = {t: _normalise_entry(v) for t, v in touchfiles.items()}

    for test, patterns in normalised.items():
        if "__ALWAYS__" in patterns:
            always.add(test)
        real = [p for p in patterns if p != "__ALWAYS__"]
        hit: list[str] = []
        for p in real:
            hit.extend(cf for cf in changed if _match(p, cf))
        if hit:
            matched[test] = sorted(set(hit))

    covered: set[str] = set()
    for patterns in normalised.values():
        real = [p for p in patterns if p != "__ALWAYS__"]
        for cf in changed:
            if any(_match(p, cf) for p in real):
                covered.add(cf)
    unmapped = set(changed) - covered

    if not changed:
        if fallback_all_tests is not None:
            selected = list(sorted(set(fallback_all_tests) | always))
            return SelectionResult(selected, tuple(sorted(always)), {}, ())
        return SelectionResult(tuple(sorted(always)), tuple(sorted(always)), {}, ())

    selected = sorted(set(matched.keys()) | always)
    return SelectionResult(
        selected=selected,
        always_run=tuple(sorted(always)),
        matched=matched,
        unmapped_changes=tuple(sorted(unmapped)),
    )


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Select tests impacted by the current diff.")
    ap.add_argument("--base", default=os.environ.get("VIBECODE_DIFF_BASE", "origin/main"))
    ap.add_argument("--map", required=True, help="Path to touchfiles JSON.")
    ap.add_argument(
        "--always", action="append", default=[], help="Extra test(s) that must always run."
    )
    ap.add_argument(
        "--fallback-all-tests-file",
        default=None,
        help="One test per line; used when the diff is empty.",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    tmap = load_map(args.map)
    changed = git_changed_files(args.base)
    fallback = None
    if args.fallback_all_tests_file:
        fallback = [
            line.strip()
            for line in Path(args.fallback_all_tests_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    res = select_tests(changed, tmap, extra_always_run=args.always, fallback_all_tests=fallback)
    if args.json:
        print(json.dumps({"changed_files": changed, **res.as_dict()}, ensure_ascii=False, indent=2))
    else:
        for t in res.selected:
            print(t)
        if res.unmapped_changes:
            sys.stderr.write(
                f"# {len(res.unmapped_changes)} changed file(s) not covered by any test mapping:\n"
            )
            for cf in res.unmapped_changes:
                sys.stderr.write(f"#   {cf}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
