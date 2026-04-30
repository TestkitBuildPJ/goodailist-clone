"""Auto-commit hook for VibecodeKit (introduced v0.11.0 Phase α — F3, current at v0.15.4).

Borrowed pattern from taw-kit (`hooks/post-tool-auto-commit.sh`) and
strengthened with:

- ``SensitiveFileGuard`` — pre-write guard so secrets never reach disk in
  the first place (taw only blocks at post-tool, after the file is written).
- Cloud-creds patterns (AWS / GCP / Azure / Stripe / Anthropic).
- ``[vibecode-auto]`` commit-message tag for easy git-log filtering.
- Structured ``Decision`` dataclass instead of bash exit codes — tests can
  introspect *why* a commit was skipped.
- Opt-out via ``VIBECODE_NO_AUTOCOMMIT=1`` (mirror taw) **or**
  ``VIBECODE_AUTOCOMMIT=0``.

This is a pure-Python reimagining; no shell-out for the policy decision.
The commit itself still uses ``git`` via ``subprocess`` because that is
the only reliable way to drive a working tree.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import time
from pathlib import Path

# --- Sensitive-file patterns ------------------------------------------------
# Tested against the *basename* and *full posix path*.  Patterns extend the
# taw-kit list with cloud-creds the original missed.
SENSITIVE_PATTERNS: tuple[str, ...] = (
    # taw-kit baseline
    r"^\.env(\..+)?$",
    r"\.key$",
    r"\.pem$",
    r"\.p12$",
    r"\.pfx$",
    r"^id_rsa(\.pub)?$",
    r"^id_ed25519(\.pub)?$",
    r"^id_ecdsa(\.pub)?$",
    r"credentials(\.json)?$",
    r"service[_-]account(\.json)?$",
    # VibecodeKit additions
    r"\.aws/credentials$",
    r"\.aws/config$",
    r"\.gcp/.*\.json$",
    r"gcloud/credentials\.db$",
    r"\.azure/.*\.json$",
    r"\.kube/config$",
    r"\.docker/config\.json$",
    r"\.netrc$",
    r"\.npmrc$",  # may carry _authToken
    r"\.pypirc$",
    r"id_rsa\b",  # bare match anywhere in path
    # Stripe / Anthropic / OpenAI / GitHub long-lived tokens via filename
    r"(stripe|anthropic|openai)[._-]?(secret|key|token)\.txt$",
)
# Compile once.
_SENSITIVE_RE = re.compile("|".join(f"(?:{p})" for p in SENSITIVE_PATTERNS))

# Whitelist (must NOT be treated as sensitive even though they match the
# regex above).  Example: ``.env.example`` is the canonical "share this file
# in the repo" convention.
_WHITELIST_RE = re.compile(
    r"(?:^|/)(?:\.env\.example|\.env\.sample|\.env\.template|"
    r"credentials\.example|service[_-]account\.example\.json)$"
)


def is_sensitive(path: str | os.PathLike[str]) -> bool:
    """Return True if *path* looks like a secret-bearing file.

    ``path`` can be relative or absolute; we test against both the basename
    and the posix-form of the full path so patterns like ``.aws/credentials``
    match.
    """
    p = str(path).replace("\\", "/")
    if _WHITELIST_RE.search(p):
        return False
    base = p.rsplit("/", 1)[-1]
    return bool(_SENSITIVE_RE.search(base) or _SENSITIVE_RE.search(p))


# --- Decision dataclass -----------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Decision:
    commit: bool
    reason: str
    files: tuple[str, ...] = ()
    debounced_remaining_s: float = 0.0


# --- Sensitive-file guard (pre-write) --------------------------------------
class SensitiveFileGuard:
    """Pre-write guard.  Call ``check(path, content=None)`` *before* writing.

    Raises ``PermissionError`` (a stdlib exception so callers can ``except
    PermissionError`` without importing this module) when the path is
    sensitive.

    Optional ``content`` check: if the proposed write *body* contains a
    high-entropy AKIA / sk-/ ghp_ / xoxb token it is also blocked, even
    when the filename itself is benign.
    """

    # High-entropy token markers.  Conservative — we want very few
    # false-positives.
    _TOKEN_MARKERS = (
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key
        re.compile(r"\bASIA[0-9A-Z]{16}\b"),  # AWS STS
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),  # OpenAI/Anthropic
        re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),  # GitHub PAT
        re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
        re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
        re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),  # Google API
    )

    def check(self, path: str | os.PathLike[str], content: str | None = None) -> None:
        if is_sensitive(path):
            raise PermissionError(f"sensitive file refused by SensitiveFileGuard: {path}")
        if content is None:
            return
        for rx in self._TOKEN_MARKERS:
            if rx.search(content):
                raise PermissionError(
                    f"high-entropy secret-like token detected in proposed "
                    f"write to {path} (matched pattern: {rx.pattern!r})"
                )


# --- Auto-commit hook -------------------------------------------------------
DEFAULT_DEBOUNCE_S = 60.0
_STAMP_PATH = ".git/.vibecode-last-autocommit"


def _opt_out() -> bool:
    if os.environ.get("VIBECODE_NO_AUTOCOMMIT") == "1":
        return True
    if os.environ.get("VIBECODE_AUTOCOMMIT") == "0":
        return True
    return False


def _is_git_repo(repo: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_status_files(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return []
    files = []
    for line in proc.stdout.splitlines():
        # Format: "XY path" — XY is 2 chars, then space, then path.
        if len(line) > 3:
            files.append(line[3:].strip())
    return files


class AutoCommitHook:
    """Decision engine for auto-committing after a write/edit.

    Policy (mirrors taw, with VBK strengthening):

    1. If opt-out env var → skip.
    2. If not inside a git repo → skip.
    3. If staged or working-tree files match sensitive patterns → REFUSE
       (do not commit, do not bump stamp; user gets a clear reason).
    4. If last commit was less than ``debounce_s`` seconds ago → skip
       (debounce the "10 commits per minute" spam).
    5. Otherwise → commit with tag ``[vibecode-auto] …``.
    """

    def __init__(
        self, debounce_s: float = DEFAULT_DEBOUNCE_S, message_prefix: str = "[vibecode-auto]"
    ):
        self.debounce_s = float(debounce_s)
        self.message_prefix = message_prefix

    # ---- decision -------------------------------------------------------
    def decide(self, repo: Path, now: float | None = None) -> Decision:
        if _opt_out():
            return Decision(False, "opt-out via env var")
        if not _is_git_repo(repo):
            return Decision(False, "not a git repo")
        files = _git_status_files(repo)
        if not files:
            return Decision(False, "nothing to commit")
        sensitive = [f for f in files if is_sensitive(f)]
        if sensitive:
            return Decision(
                False, f"sensitive files in working tree: {sensitive}", files=tuple(sensitive)
            )
        # Debounce
        stamp = repo / _STAMP_PATH
        now_s = float(now) if now is not None else time.time()
        if stamp.is_file():
            try:
                last = float(stamp.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                last = 0.0
            elapsed = now_s - last
            if elapsed < self.debounce_s:
                return Decision(
                    False,
                    f"debounced (last commit {elapsed:.1f}s ago, "
                    f"threshold {self.debounce_s:.1f}s)",
                    files=tuple(files),
                    debounced_remaining_s=self.debounce_s - elapsed,
                )
        return Decision(True, "ready to commit", files=tuple(files))

    # ---- action ---------------------------------------------------------
    def commit(self, repo: Path, message: str = "checkpoint", now: float | None = None) -> Decision:
        decision = self.decide(repo, now=now)
        if not decision.commit:
            return decision
        # Stage everything we saw, but explicitly do NOT use ``git add .``
        # — pass the files we already validated.
        full_msg = f"{self.message_prefix} {message}".strip()
        try:
            subprocess.run(
                ["git", "add", "--", *decision.files],
                cwd=str(repo),
                check=True,
                capture_output=True,
                timeout=15,
            )
            subprocess.run(
                ["git", "commit", "--no-verify", "-m", full_msg],
                cwd=str(repo),
                check=True,
                capture_output=True,
                timeout=15,
            )
        except subprocess.CalledProcessError as exc:
            return Decision(
                False,
                f"git commit failed: {exc.stderr.decode('utf-8', 'replace') if exc.stderr else exc!r}",
                files=decision.files,
            )
        # Bump stamp
        stamp = repo / _STAMP_PATH
        now_s = float(now) if now is not None else time.time()
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(f"{now_s:.6f}\n", encoding="utf-8")
        return Decision(True, f"committed {len(decision.files)} files", files=decision.files)


__all__ = [
    "is_sensitive",
    "SensitiveFileGuard",
    "AutoCommitHook",
    "Decision",
    "SENSITIVE_PATTERNS",
    "DEFAULT_DEBOUNCE_S",
]
