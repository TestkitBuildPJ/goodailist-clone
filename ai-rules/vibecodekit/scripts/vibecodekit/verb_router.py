"""Unified ``/vibe <verb>`` front-door — thin verb-to-command router.

Th\u00eam **front-door** d\u1ea1ng ``/vibe <verb> [args...]`` map 8 verb chu\u1ea9n
t\u1edbi slash command canonical t\u01b0\u01a1ng \u1ee9ng.  M\u1ee5c \u0111\u00edch:

* Gi\u1ea3m friction tr\u00ed nh\u1edb (4-5 t\u1eeb thay v\u00ec 42 slash command).
* T\u00e1ch front-door (verb) v\u1edbi back-end (slash command t\u00ean d\u00e0i):
  user g\u00f5 ``/vibe ship`` \u2192 router tr\u1ea3 ``/vck-ship`` \u2192 invoke c\u00f3 th\u1ec3
  swap canonical sau (vd. r\u00fat ``/vibe-ship`` xu\u1ed1ng ``/vck-ship``)
  m\u00e0 user kh\u00f4ng nh\u1eadn ra.
* **Additive, non-breaking**: 42 slash command c\u0169 v\u1eabn invokable.

8 verb \u0111\u01b0\u1ee3c support:

| Verb       | Canonical slash command   | Pipeline step (VIBECODE-MASTER v5) |
|------------|---------------------------|------------------------------------|
| ``scan``   | ``/vibe-scan``            | Step 1: read-only scout pass       |
| ``plan``   | ``/vibe-blueprint``       | Step 4: architecture + interfaces  |
| ``build``  | ``/vibe-scaffold``        | Step 6: implement TIP              |
| ``review`` | ``/vck-review``           | Adversarial multi-specialist       |
| ``qa``     | ``/vck-qa``               | Real-browser QA + fix loop         |
| ``ship``   | ``/vck-ship``             | test \u2192 review \u2192 commit \u2192 PR     |
| ``audit``  | ``/vibe-audit``           | 87-probe internal self-test        |
| ``doctor`` | ``/vibe-doctor``          | overlay health check               |

L\u01b0u \u00fd
------

* ``ship`` map sang ``/vck-ship`` (full pipeline) thay v\u00ec
  ``/vibe-ship`` (deploy-only): deprecate marker tr\u00ean
  ``vibe-ship.md`` \u0111\u00e3 ghi r\u00f5 canonical \u1edf PR4.
* ``build`` map sang ``/vibe-scaffold`` thay v\u00ec ``/vibe-build`` (kh\u00f4ng
  t\u1ed3n t\u1ea1i): scaffold-from-preset l\u00e0 b\u01b0\u1edbc build canonical hi\u1ec7n c\u00f3.
* Verb kh\u00f4ng h\u1ee3p l\u1ec7 raise ``ValueError`` v\u1edbi list 8 verb \u0111\u00fang.
* ``args`` \u0111\u01b0\u1ee3c forward verbatim qua command \u0111\u00edch \u2014 router KH\u00d4NG
  parse / KH\u00d4NG validate; semantic n\u1eb1m \u1edf command target.
"""

from __future__ import annotations

from collections.abc import Iterable

# Canonical verb \u2192 slash command map.  Key \u0111\u00fang spelling, value n\u1eb1m
# trong ``update-package/.claude/commands/<name>.md`` (kh\u00f4ng ``deprecated:
# true``).  Test ``test_verb_router_targets_exist`` enforce \u0111i\u1ec1u ki\u1ec7n.
_VERB_TO_COMMAND: dict[str, str] = {
    "scan": "/vibe-scan",
    "plan": "/vibe-blueprint",
    "build": "/vibe-scaffold",
    "review": "/vck-review",
    "qa": "/vck-qa",
    "ship": "/vck-ship",
    "audit": "/vibe-audit",
    "doctor": "/vibe-doctor",
}

SUPPORTED_VERBS: tuple[str, ...] = tuple(sorted(_VERB_TO_COMMAND.keys()))


class UnknownVerbError(ValueError):
    """Verb kh\u00f4ng n\u1eb1m trong ``SUPPORTED_VERBS``."""


def route_verb(verb: str, args: Iterable[str] | None = None) -> list[str]:
    """Map ``verb`` \u2192 ``[slash-command, *args]``.

    Examples
    --------
    >>> route_verb("scan")
    ['/vibe-scan']
    >>> route_verb("ship", ["--target", "vercel"])
    ['/vck-ship', '--target', 'vercel']
    >>> route_verb("plan", [])
    ['/vibe-blueprint']

    Raises
    ------
    UnknownVerbError
        N\u1ebfu ``verb`` kh\u00f4ng thu\u1ed9c ``SUPPORTED_VERBS``.  Message g\u1ee3i
        \u00fd 8 verb h\u1ee3p l\u1ec7.
    """
    key = verb.strip().lower()
    if key not in _VERB_TO_COMMAND:
        raise UnknownVerbError(
            f"Unknown verb: {verb!r}.  Supported verbs: " f"{', '.join(SUPPORTED_VERBS)}."
        )
    out = [_VERB_TO_COMMAND[key]]
    if args:
        out.extend(str(a) for a in args)
    return out


def help_text() -> str:
    """Return song ng\u1eef help text (VN tr\u01b0\u1edbc, EN sau) cho ``vibe verb``."""
    return _HELP_TEXT


_HELP_TEXT = """\
/vibe <verb>  \u2014 unified front-door / c\u1eeda v\u00e0o th\u1ed1ng nh\u1ea5t

VN: Front-door cho 8 verb chu\u1ea9n; map t\u1edbi slash command canonical
    t\u01b0\u01a1ng \u1ee9ng.  Verb args (n\u1ebfu c\u00f3) \u0111\u01b0\u1ee3c forward verbatim.

EN: Front-door for 8 canonical verbs; maps to the canonical slash
    command.  Verb args (if any) are forwarded verbatim.

Verbs (8):

  scan      \u2192 /vibe-scan        VN: scan repo + docs (b\u01b0\u1edbc 1)
                                  EN: scout pass over repo + docs

  plan      \u2192 /vibe-blueprint   VN: blueprint architecture + interfaces
                                  EN: architecture + data + interfaces

  build     \u2192 /vibe-scaffold    VN: scaffold project t\u1eeb preset
                                  EN: scaffold runnable starter

  review    \u2192 /vck-review       VN: adversarial 7-specialist review
                                  EN: adversarial multi-specialist code review

  qa        \u2192 /vck-qa           VN: real-browser QA checklist + fix loop
                                  EN: real-browser QA + fix loop

  ship      \u2192 /vck-ship         VN: test \u2192 review \u2192 commit \u2192 push \u2192 PR
                                  EN: test \u2192 review \u2192 commit \u2192 push \u2192 PR

  audit     \u2192 /vibe-audit       VN: 87-probe internal conformance self-test
                                  EN: 87-probe internal regression gate

  doctor    \u2192 /vibe-doctor      VN: ki\u1ec3m tra overlay c\u00e0i \u0111\u00fang
                                  EN: overlay health check

V\u00ed d\u1ee5 / Examples:

  vibe verb scan
  vibe verb plan
  vibe verb ship --target vercel --prod
  vibe verb audit --threshold 1.0

Backward compat:
  VN: 42 slash command c\u0169 v\u1eabn invokable. /vibe-ship, /vibe-rri-t,
      /vibe-rri-ui, /vibe-rri-ux \u0111\u00e3 deprecated (xem PR4) \u2014 v\u1eabn ch\u1ea1y
      \u0111\u1ebfn v1.0.0; tu\u1ea7n t\u1ef1 migrate sang /vck-ship, /vibe-rri.
  EN: All 42 legacy slash commands remain invokable.  Four are
      deprecated (see PR4); migrate at your pace before v1.0.0.
"""
