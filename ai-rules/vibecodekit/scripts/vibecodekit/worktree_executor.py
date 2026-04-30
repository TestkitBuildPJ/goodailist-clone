"""Git worktree isolation for parallel agents (Pattern #8).

Creates a worktree in ``.vibecode/runtime/worktrees/<id>/`` so several
sub-agents can mutate the same repo in parallel without stepping on each
other.  The command is always ``git worktree add`` — we never use
``--force``; cleanup is explicit via :func:`remove`.

References:
- ``references/08-fork-isolation-worktree.md``
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

# v0.10.4: all git subprocess calls get a 30 s wall-clock timeout so a
# hung hook or a broken ``git`` binary can't freeze the runtime.
_GIT_TIMEOUT_S = 30.0


def _gitroot(path: Path) -> Path:
    p = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
        timeout=_GIT_TIMEOUT_S,
    )
    return Path(p.stdout.strip())


def create(root: str | os.PathLike, slug: str, base: str | None = None) -> dict[str, str]:
    root = Path(root).resolve()
    gr = _gitroot(root)
    worktrees = gr / ".vibecode" / "runtime" / "worktrees"
    worktrees.mkdir(parents=True, exist_ok=True)
    target = worktrees / f"{slug}-{int(time.time())}"
    branch = f"vibe/{slug}-{int(time.time())}"
    cmd = ["git", "-C", str(gr), "worktree", "add", "-b", branch, str(target)]
    if base:
        cmd.append(base)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=_GIT_TIMEOUT_S)
    return {
        "returncode": p.returncode,
        "stdout": p.stdout,
        "stderr": p.stderr,
        "worktree": str(target.relative_to(gr)),
        "branch": branch,
    }


def remove(root: str | os.PathLike, worktree_rel: str) -> dict[str, str]:
    root = Path(root).resolve()
    gr = _gitroot(root)
    target = gr / worktree_rel
    cmd = ["git", "-C", str(gr), "worktree", "remove", str(target)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=_GIT_TIMEOUT_S)
    # Best-effort directory cleanup if git left residue.
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    return {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def list_worktrees(root: str | os.PathLike) -> dict[str, str]:
    root = Path(root).resolve()
    gr = _gitroot(root)
    p = subprocess.run(
        ["git", "-C", str(gr), "worktree", "list"],
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT_S,
    )
    return {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
