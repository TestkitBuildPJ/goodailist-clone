"""Machine-executable helpers for the v0.10 methodology layer.

v0.10.0 shipped the references and templates for RRI / RRI-T / RRI-UX /
RRI-UI / VIBECODE-MASTER, but they were author-only — humans read
the templates and produced docs.  v0.10.1 adds three runners that turn
those templates into machine-checkable artefacts:

1. ``RRI-T`` runner — reads a ``.jsonl`` of ``{id, persona, dimension,
   stress, result}`` entries, scores each dimension by ``pass / total``
   against the release gate (≥ 70 % per dim, at least 5/7 ≥ 85 %, 0 P0).
2. ``RRI-UX`` runner — same shape, 🌊 FLOW counts instead of ✅ PASS.
3. ``Vietnamese 12-point checklist`` — evaluates a built artefact
   (JSON dict of ``flag: bool``) against the 12 mandatory rules in
   ``references/32-rri-ux-critique.md`` §9.

Plus a small ``config.py``-like helper that persists the preferred
embedding backend to ``~/.vibecode/config.json`` so CLI calls don't
have to re-pass ``--backend`` every time.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# Public API surface (PR3 / sau review #4).  Bất cứ symbol public-ish nào
# KHÔNG nằm trong ``__all__`` đều được coi là internal — re-tooling /
# refactor không cần PR mới.  Thêm symbol mới vào danh sách này phải kèm
# test smoke trong ``tests/test_methodology_public_api.py``.
__all__ = (
    # Schema constants (dataclass-style — chỉ doc, không evaluate runtime).
    "RRI_T_DIMENSIONS",
    "RRI_T_STRESS_AXES",
    "RRI_T_RESULT_LEVELS",
    "RRI_UX_AXES",
    "RRI_UX_DIMENSIONS",
    "RRI_UX_RESULT_LEVELS",
    # RRI runners (3 lõi methodology — public lock).
    "evaluate_rri_t",
    "evaluate_rri_ux",
    "evaluate_vn_checklist",
    # Anti-patterns + verify coverage.
    "anti_patterns_canonical",
    "evaluate_anti_patterns_checklist",
    "evaluate_verify_coverage",
    # Config persistence (CLI + downstream consumers).
    "config_path",
    "load_config",
    "save_config",
    "set_config",
    "get_config_value",
    "set_embedding_backend",
    "get_embedding_backend",
    # Style tokens + reference loader.
    "lookup_style_token",
    "list_references",
    "load_reference",
    "load_reference_section",
    # RRI question bank + stack recommender.
    "load_rri_questions",
    "list_rri_question_project_types",
    "recommend_stack",
    "list_stack_recommendations",
    # Command context composer.
    "list_wired_commands",
    "render_command_context",
)


# ---------------------------------------------------------------------------
# RRI-T runner
# ---------------------------------------------------------------------------

RRI_T_DIMENSIONS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7")
RRI_T_STRESS_AXES = (
    "TIME",
    "DATA",
    "ERROR",
    "COLLAB",
    "EMERGENCY",
    "SECURITY",
    "INFRASTRUCTURE",
    "LOCALIZATION",
)
RRI_T_RESULT_LEVELS = {"PASS", "FAIL", "PAINFUL", "MISSING"}


def _read_jsonl(path: os.PathLike | str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    with p.open("r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"line {i}: {e}") from e
    return out


def _score_dimensions(
    entries: Iterable[dict[str, Any]], dimensions: tuple[str, ...], good_results: tuple[str, ...]
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {d: {"total": 0, "good": 0} for d in dimensions}
    for e in entries:
        dim = e.get("dimension")
        if dim not in counts:
            continue
        counts[dim]["total"] += 1
        if (e.get("result") or "").upper() in good_results:
            counts[dim]["good"] += 1
    return counts


def _percent(good: int, total: int) -> float:
    return (good / total * 100.0) if total else 0.0


def evaluate_rri_t(path: os.PathLike | str) -> dict[str, Any]:
    """Score a RRI-T test log against the release gate.

    Gate (ref 31, §7):
      * Every dimension covered by ≥ 1 entry (no missing dims)
      * Every dimension ≥ 70 % PASS
      * ≥ 5 / 7 dimensions ≥ 85 % PASS
      * 0 P0 FAIL items

    Returns ``{"summary": {...}, "per_dimension": {...}, "gate": "PASS"|"FAIL", "reasons": [...]}``.
    """
    entries = _read_jsonl(path)
    counts = _score_dimensions(entries, RRI_T_DIMENSIONS, ("PASS",))
    per_dim: dict[str, dict[str, Any]] = {}
    for d, c in counts.items():
        per_dim[d] = {
            "good": c["good"],
            "total": c["total"],
            "percent": round(_percent(c["good"], c["total"]), 2),
        }
    dim_pct = [per_dim[d]["percent"] for d in RRI_T_DIMENSIONS if per_dim[d]["total"] > 0]
    reasons: list[str] = []
    # Gate #0 (v0.10.2): every dimension must be exercised at all.
    missing = [d for d in RRI_T_DIMENSIONS if per_dim[d]["total"] == 0]
    if missing:
        reasons.append(f"no entries for dimensions: {missing}")
    # Gate #1
    below_70 = [
        d for d in RRI_T_DIMENSIONS if per_dim[d]["total"] > 0 and per_dim[d]["percent"] < 70
    ]
    if below_70:
        reasons.append(f"dimensions < 70 %: {below_70}")
    # Gate #2
    at_85 = sum(
        1 for d in RRI_T_DIMENSIONS if per_dim[d]["total"] > 0 and per_dim[d]["percent"] >= 85
    )
    if at_85 < 5:
        reasons.append(f"only {at_85}/7 dimensions ≥ 85 %")
    # Gate #3
    p0_fails = [
        e
        for e in entries
        if (e.get("priority") or "").upper() == "P0" and (e.get("result") or "").upper() == "FAIL"
    ]
    if p0_fails:
        reasons.append(f"{len(p0_fails)} P0 FAIL")
    total = len(entries)
    passed = sum(1 for e in entries if (e.get("result") or "").upper() == "PASS")
    return {
        "summary": {
            "total": total,
            "pass": passed,
            "overall_percent": round(_percent(passed, total), 2),
            "dimensions_evaluated": len(dim_pct),
        },
        "per_dimension": per_dim,
        "missing_dimensions": missing,
        "p0_fails": [e.get("id", "?") for e in p0_fails],
        "gate": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# RRI-UX runner
# ---------------------------------------------------------------------------

RRI_UX_DIMENSIONS = ("U1", "U2", "U3", "U4", "U5", "U6", "U7")
RRI_UX_AXES = (
    "SCROLL",
    "CLICK DEPTH",
    "EYE TRAVEL",
    "DECISION LOAD",
    "RETURN PATH",
    "VIEWPORT",
    "VN TEXT",
    "FEEDBACK",
)
RRI_UX_RESULT_LEVELS = {"FLOW", "FRICTION", "BROKEN", "MISSING"}


def evaluate_rri_ux(path: os.PathLike | str) -> dict[str, Any]:
    """Score a RRI-UX critique log against the release gate.

    Gate (ref 32, §8):
      * Every dimension covered by ≥ 1 entry (no missing dims)
      * Every dimension ≥ 70 % FLOW
      * ≥ 5 / 7 dimensions ≥ 85 % FLOW
      * 0 P0 BROKEN items
    """
    entries = _read_jsonl(path)
    counts = _score_dimensions(entries, RRI_UX_DIMENSIONS, ("FLOW",))
    per_dim = {
        d: {
            "good": c["good"],
            "total": c["total"],
            "percent": round(_percent(c["good"], c["total"]), 2),
        }
        for d, c in counts.items()
    }
    reasons: list[str] = []
    missing = [d for d in RRI_UX_DIMENSIONS if per_dim[d]["total"] == 0]
    if missing:
        reasons.append(f"no entries for dimensions: {missing}")
    below_70 = [
        d for d in RRI_UX_DIMENSIONS if per_dim[d]["total"] > 0 and per_dim[d]["percent"] < 70
    ]
    if below_70:
        reasons.append(f"dimensions < 70 %: {below_70}")
    at_85 = sum(
        1 for d in RRI_UX_DIMENSIONS if per_dim[d]["total"] > 0 and per_dim[d]["percent"] >= 85
    )
    if at_85 < 5:
        reasons.append(f"only {at_85}/7 dimensions ≥ 85 %")
    p0_broken = [
        e
        for e in entries
        if (e.get("priority") or "").upper() == "P0" and (e.get("result") or "").upper() == "BROKEN"
    ]
    if p0_broken:
        reasons.append(f"{len(p0_broken)} P0 BROKEN")
    total = len(entries)
    flows = sum(1 for e in entries if (e.get("result") or "").upper() == "FLOW")
    return {
        "summary": {
            "total": total,
            "flow": flows,
            "overall_percent": round(_percent(flows, total), 2),
            "dimensions_evaluated": len([d for d in per_dim if per_dim[d]["total"] > 0]),
        },
        "per_dimension": per_dim,
        "missing_dimensions": missing,
        "p0_broken": [e.get("id", "?") for e in p0_broken],
        "gate": "PASS" if not reasons else "FAIL",
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# Vietnamese 12-point checklist (ref 32 §9)
# ---------------------------------------------------------------------------

VN_CHECKLIST_ITEMS = (
    ("nfkd_diacritics", "Diacritic-insensitive search (NFKD normalisation)"),
    ("address_cascade", "Address fields cascade: Tỉnh → Huyện → Xã"),
    ("vnd_formatting", "VND amounts render with '.' thousands + ' ₫' suffix"),
    ("cccd_12_digits", "CCCD / CMND validator enforces 12 / 9 digits"),
    ("date_dd_mm_yyyy", "Dates display DD/MM/YYYY (never MM/DD/YYYY)"),
    ("phone_10_digits", "Phone validator accepts +84 and local 10-digit"),
    ("longest_string_layout", "Layout tested with longest Vietnamese labels"),
    ("diacritic_sort", "Sorting respects Vietnamese collation order"),
    ("vn_money_spellout", "Optional VND spell-out matches TCVN / bank format"),
    ("holidays_lunar", "Lunar holidays supported in date pickers"),
    ("encoding_utf8", "All responses emit UTF-8 + BOM-free"),
    ("rtl_awareness", "Not applicable but declared explicit (Vietnamese is LTR)"),
)


def evaluate_vn_checklist(flags: dict[str, bool]) -> dict[str, Any]:
    """Score an artefact against the 12-point Vietnamese checklist.

    ``flags`` is a dict mapping checklist keys to a boolean.  Unknown
    keys are ignored; missing keys count as ``False``.  The gate is
    ``gate="PASS"`` iff all 12 items are ``True``; otherwise ``FAIL``
    and ``missing`` lists the failing keys.
    """
    results: list[dict[str, Any]] = []
    missing: list[str] = []
    for key, label in VN_CHECKLIST_ITEMS:
        ok = bool(flags.get(key))
        results.append({"key": key, "label": label, "pass": ok})
        if not ok:
            missing.append(key)
    passed = sum(1 for r in results if r["pass"])
    return {
        "summary": {
            "total": len(VN_CHECKLIST_ITEMS),
            "pass": passed,
            "percent": round(_percent(passed, len(VN_CHECKLIST_ITEMS)), 2),
        },
        "results": results,
        "gate": "PASS" if not missing else "FAIL",
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# 12 SaaS anti-patterns (RRI-UX § 10) — canonical list + checklist evaluator
# ---------------------------------------------------------------------------

ANTI_PATTERNS: tuple[tuple[str, str, str, str], ...] = (
    (
        "AP-01",
        "Modal-on-load",
        "Popup chặn ngay khi vào trang chủ",
        "Hero section bị overlay che ≥ 1.5 s sau load",
    ),
    (
        "AP-02",
        "Hidden CTA",
        "Primary action không xuất hiện trong viewport đầu tiên",
        "CTA dưới fold trên viewport 1366×768 / 390×844",
    ),
    (
        "AP-03",
        "Reverse-scroll trap",
        "Bước tiếp nằm phía trên bước hiện tại",
        "next-step ở top < current.top",
    ),
    (
        "AP-04",
        "Form > 7 fields, no progressive disclosure",
        "Form dài không split wizard/accordion/tab",
        "<form> có > 7 input visible đồng thời",
    ),
    (
        "AP-05",
        "Dropdown > 15 items, no search",
        "Danh sách lớn không có search",
        "<select>/combobox > 15 option mà không có filter input",
    ),
    (
        "AP-06",
        "Empty state without guidance",
        "Trạng thái rỗng không có CTA/hướng dẫn",
        "Empty container không có button/link/illustration explainer",
    ),
    (
        "AP-07",
        "Silent failure",
        "Hành động fail không có feedback",
        "4xx/5xx không update [role=alert] / toast",
    ),
    (
        "AP-08",
        "Lost session on accidental refresh",
        "Form/draft mất khi F5/back-forward",
        "Không có localStorage/sessionStorage autosave",
    ),
    (
        "AP-09",
        "Tab/filter state reset on navigation",
        "Filter/sort/pagination biến mất khi navigation",
        "URL không phản ánh filter; chỉ in-memory state",
    ),
    (
        "AP-10",
        "Touch target < 44 × 44 px",
        "Mobile bấm nhầm liên tục",
        "Click target < 44 px ở viewport ≤ 480 px",
    ),
    (
        "AP-11",
        "Date format ambiguity",
        "Không clarify DD/MM/YYYY vs MM/DD/YYYY",
        "Date input không có placeholder/aria-describedby format",
    ),
    (
        "AP-12",
        "VND format errors",
        "Số tiền hiển thị 1234567 thay vì 1.234.567 ₫",
        "Không dùng Intl.NumberFormat('vi-VN', currency: 'VND')",
    ),
)
"""Canonical 12-pattern checklist used by the SaaS release gate.

Each entry is ``(id, name, description, detection_hint)``.  IDs are
stable: never renumber; new patterns get appended as ``AP-13+``.

Cross-referenced from ``references/32-rri-ux-critique.md`` § 10.
"""


def anti_patterns_canonical() -> tuple[dict[str, str], ...]:
    """Return the canonical 12-pattern list as a tuple of dicts."""
    return tuple(
        {"id": ap_id, "name": name, "description": desc, "detection_hint": hint}
        for ap_id, name, desc, hint in ANTI_PATTERNS
    )


def evaluate_anti_patterns_checklist(
    flags: dict[str, bool] | dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the SaaS release-gate ``0/12 violations`` rule.

    ``flags`` maps anti-pattern IDs (``AP-01`` … ``AP-12``) — or their
    canonical lowercase names — to a boolean indicating whether the
    pattern was *violated* on the artefact under test.

    The gate is ``"PASS"`` iff zero violations are present.  Unknown
    keys are silently ignored (forward-compat with future patterns).
    """
    name_lookup = {ap_id.lower(): ap_id for ap_id, _, _, _ in ANTI_PATTERNS}
    name_lookup.update({name.lower(): ap_id for ap_id, name, _, _ in ANTI_PATTERNS})
    violations: list[dict[str, str]] = []
    seen: set = set()
    for raw_key, value in (flags or {}).items():
        if not value:
            continue
        key = str(raw_key).strip().lower()
        ap_id = name_lookup.get(key)
        if ap_id is None or ap_id in seen:
            continue
        seen.add(ap_id)
        meta = next(p for p in ANTI_PATTERNS if p[0] == ap_id)
        violations.append({"id": meta[0], "name": meta[1]})
    violations.sort(key=lambda v: v["id"])
    total = len(ANTI_PATTERNS)
    passed = total - len(violations)
    return {
        "total": total,
        "violations": len(violations),
        "passed": passed,
        "violations_list": violations,
        "gate": "PASS" if not violations else "FAIL",
    }


# ---------------------------------------------------------------------------
# Verify-report REQ-* coverage (v5 BƯỚC 7 traceability)
# ---------------------------------------------------------------------------

VERIFY_COVERAGE_GATE_THRESHOLD = 0.85
"""Release gate: ≥85 % of non-deferred requirements must be DONE."""

_REQ_ID_RE = re.compile(r"\bREQ-\d{3,4}\b")
_VERIFY_ROW_RE = re.compile(r"^\|\s*(REQ-\d{3,4})\s*\|" r"(?P<rest>.+)$")


def _parse_blueprint_reqs(text: str) -> list[str]:
    """Return ordered list of REQ-IDs declared in a blueprint matrix."""
    seen: list[str] = []
    in_matrix = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("##") and "RRI Requirements matrix" in stripped:
            in_matrix = True
            continue
        if in_matrix and stripped.startswith("##"):
            break
        if not in_matrix:
            continue
        m = re.match(r"^\|\s*(REQ-\d{3,4})\s*\|", line)
        if m:
            req = m.group(1)
            if req not in seen:
                seen.append(req)
    return seen


def _parse_verify_statuses(text: str) -> dict[str, dict[str, str]]:
    """Return ``{REQ-ID: {"status": ..., "evidence": ...}}`` from a
    verify report.  Looks for rows in the traceability matrix table.
    """
    out: dict[str, dict[str, str]] = {}
    in_matrix = False
    valid = {"DONE", "PARTIAL", "MISSING", "DEFERRED"}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("##") and (
            "Requirement traceability" in stripped or "Traceability matrix" in stripped
        ):
            in_matrix = True
            continue
        if in_matrix and stripped.startswith("##"):
            break
        if not in_matrix:
            continue
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 3:
            continue
        req = cells[0]
        if not _REQ_ID_RE.fullmatch(req):
            continue
        status_cell = cells[2].upper()
        # Status cell may contain "DONE / PARTIAL ..." legend on the
        # template row — treat any cell with multiple keywords as
        # unspecified.
        words = re.findall(r"[A-Z]+", status_cell)
        chosen = next((w for w in words if w in valid), None)
        # Skip the canonical legend row that lists every status.
        if chosen is None or sum(1 for w in words if w in valid) > 1:
            continue
        evidence = cells[3] if len(cells) > 3 else ""
        out[req] = {"status": chosen, "evidence": evidence}
    return out


def evaluate_verify_coverage(
    matrix_path: os.PathLike | str,
    report_path: os.PathLike | str,
    *,
    threshold: float = VERIFY_COVERAGE_GATE_THRESHOLD,
) -> dict[str, Any]:
    """Check that the verify report exhausts the blueprint REQ matrix.

    Returns a dict with keys::

        total, done, partial, missing, deferred,
        coverage_pct,           # DONE / (total - deferred), rounded to 2 dp
        gate,                   # "PASS" | "FAIL"
        missing_ids, partial_ids, deferred_ids,
        unknown_ids,            # rows in report not in blueprint
        threshold

    Gate is PASS iff ``missing == 0`` AND
    ``coverage_pct >= threshold * 100``.
    """
    matrix_text = Path(matrix_path).read_text(encoding="utf-8")
    report_text = Path(report_path).read_text(encoding="utf-8")
    declared = _parse_blueprint_reqs(matrix_text)
    statuses = _parse_verify_statuses(report_text)

    done: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    deferred: list[str] = []
    for req in declared:
        st = statuses.get(req, {"status": "MISSING"})["status"]
        if st == "DONE":
            done.append(req)
        elif st == "PARTIAL":
            partial.append(req)
        elif st == "DEFERRED":
            deferred.append(req)
        else:
            missing.append(req)

    unknown = sorted(set(statuses.keys()) - set(declared))

    total = len(declared)
    denom = total - len(deferred)
    coverage_pct = round(_percent(len(done), denom), 2) if denom else 0.0

    gate_passed = not missing and coverage_pct >= round(threshold * 100.0, 2)
    return {
        "total": total,
        "done": len(done),
        "partial": len(partial),
        "missing": len(missing),
        "deferred": len(deferred),
        "coverage_pct": coverage_pct,
        "gate": "PASS" if gate_passed else "FAIL",
        "missing_ids": missing,
        "partial_ids": partial,
        "deferred_ids": deferred,
        "done_ids": done,
        "unknown_ids": unknown,
        "threshold": threshold,
    }


# ---------------------------------------------------------------------------
# Persistent config (~/.vibecode/config.json)
# ---------------------------------------------------------------------------

_CONFIG_ENV = "VIBECODE_CONFIG_HOME"
_CONFIG_REL = "config.json"


def _config_dir() -> Path:
    base = os.environ.get(_CONFIG_ENV)
    if base:
        return Path(base).expanduser().resolve()
    return Path.home() / ".vibecode"


def config_path() -> Path:
    return _config_dir() / _CONFIG_REL


def load_config() -> dict[str, Any]:
    p = config_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: dict[str, Any]) -> Path:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    return p


def set_config(**kwargs: Any) -> dict[str, Any]:
    cfg = load_config()
    cfg.update({k: v for k, v in kwargs.items() if v is not None})
    save_config(cfg)
    return cfg


def get_config_value(key: str, default: Any = None) -> Any:
    return load_config().get(key, default)


# Convenience --------------------------------------------------------------

KNOWN_EMBEDDING_BACKENDS = (
    "hash-256",  # default pure-Python deterministic
    "sentence-transformers",  # reserved: caller registers at runtime
    "openai",  # reserved
    "cohere",  # reserved
    "sbert-multilingual",  # reserved
)


def set_embedding_backend(name: str) -> dict[str, Any]:
    if name not in KNOWN_EMBEDDING_BACKENDS:
        raise ValueError(f"unknown backend: {name!r}; known: {KNOWN_EMBEDDING_BACKENDS}")
    return set_config(embedding_backend=name)


def get_embedding_backend(default: str = "hash") -> str:
    return str(get_config_value("embedding_backend", default))


# ---------------------------------------------------------------------------
# Style tokens (v0.11.1, port of references/34-style-tokens.md / master v5 §B/C/D)
# ---------------------------------------------------------------------------

FONT_PAIRINGS: dict[str, tuple[str, str, str]] = {
    "FP-01": ("Plus Jakarta Sans", "Inter", "Modern Tech"),
    "FP-02": ("DM Sans", "Source Sans Pro", "Professional"),
    "FP-03": ("Playfair Display", "Lato", "Creative"),
    "FP-04": ("Poppins", "Open Sans", "Friendly"),
    "FP-05": ("Cormorant Garamond", "Montserrat", "Elegant"),
    "FP-06": ("Space Grotesk", "Work Sans", "Startup"),
}

COLOR_PSYCHOLOGY: dict[str, tuple[str, str]] = {
    "CP-01": ("Trust/Professional", "#2563EB"),
    "CP-02": ("Energy/Action", "#F97316"),
    "CP-03": ("Growth/Health", "#22C55E"),
    "CP-04": ("Luxury/Premium", "#7C3AED"),
    "CP-05": ("Warning/Urgency", "#EF4444"),
    "CP-06": ("Neutral/Modern", "#6B7280"),
}

COPY_PATTERNS: dict[str, str] = {
    "CF-01": "[Số] + [Timeframe] + [Outcome]",
    "CF-02": "[Verb] + [Object] + [Benefit]",
    "CF-03": "[Question that resonates]",
    "CF-04": "[Action verb] + [Value]",
    "CF-05": "Logo bar 5-7 logos",
    "CF-06": "Testimonial: face + quote ≤25 từ + role + company (with concrete number)",
    # v0.11.2 / FIX-005 additions
    "CF-07": "[Tier] · [Price] · [Unit] · [Anchor benefit ≤ 6 words]",
    "CF-08": "[Verb] + [Outcome] + CTA; never 'No data' / 'Empty'",
    "CF-09": "[What happened ≤ 12 words] + [What to do ≤ 8 words] + [Optional trace ID]",
}

# Vietnamese-first copy rules (v0.11.2 / FIX-005, port of master v5 §D + ref-36 §7)
COPY_PATTERNS_VN: dict[str, str] = {
    "CF-VN-01": "Use 'Bạn' / product name; never 'user' / 'system' in user-facing copy",
    "CF-VN-02": "Default 2nd-person pronoun: 'Bạn' (informal-respectful) — 'Quý khách' only B2B/legal",
    "CF-VN-03": "Pluralisation: 'các <X>' — Vietnamese has no plural-s",
    "CF-VN-04": "Times: 24h dashboards / 12h+sáng/chiều/tối consumer; dates dd/MM/yyyy",
    "CF-VN-05": "VND format: '199.000\u00a0₫'; mixed currency keeps '$' but localises '/mo' → '/tháng'",
    "CF-VN-06": "Punctuation: dấu sát chữ; ':' has trailing space, no leading space",
    "CF-VN-07": "Capitalisation: only first letter + proper nouns — never title-case Vietnamese",
    "CF-VN-08": "Avoid borrowed jargon (onboarding/churn/retention) in user-facing VN copy",
}


def lookup_style_token(token_id: str) -> dict[str, Any] | None:
    """Look up FP-/CP-/CF- by ID. Returns None if unknown."""
    if token_id.startswith("FP-") and token_id in FONT_PAIRINGS:
        h, b, mood = FONT_PAIRINGS[token_id]
        return {"id": token_id, "kind": "font_pairing", "heading": h, "body": b, "mood": mood}
    if token_id.startswith("CP-") and token_id in COLOR_PSYCHOLOGY:
        meaning, hex_ = COLOR_PSYCHOLOGY[token_id]
        return {"id": token_id, "kind": "color_psychology", "meaning": meaning, "hex": hex_}
    if token_id.startswith("CF-") and token_id in COPY_PATTERNS:
        return {"id": token_id, "kind": "copy_pattern", "formula": COPY_PATTERNS[token_id]}
    return None


# ---------------------------------------------------------------------------
# RRI base question bank (v0.11.1, port of master v5 §E)
# ---------------------------------------------------------------------------


def _question_bank_path() -> Path:
    env = os.environ.get("VIBECODE_SKILL_ROOT")
    if env:
        return Path(env) / "assets" / "rri-question-bank.json"
    here = Path(__file__).resolve()
    skill_root = here.parents[2]
    return skill_root / "assets" / "rri-question-bank.json"


_RRI_PROJECT_ALIASES: dict[str, str] = {
    "landing-page": "landing",
    "marketing": "landing",
    "saas-app": "saas",
    "saas-product": "saas",
    "admin": "dashboard",
    "analytics": "dashboard",
    "blog-site": "blog",
    "writing": "blog",
    "docs-site": "docs",
    "documentation": "docs",
    "knowledge-base": "docs",
    "personal": "portfolio",
    "showcase": "portfolio",
    "shop": "ecommerce",
    "shop-online": "ecommerce",
    "store": "ecommerce",
    "module": "enterprise-module",
    "feature": "enterprise-module",
    "enterprise": "enterprise-module",
    # v0.11.4 Obs-1: presets that previously fell back to ``custom`` (16 q)
    # now resolve to dedicated banks (~30 q each, 5 personas × 3 modes).
    "api-todo": "api",
    "rest-api": "api",
    "backend": "api",
    "crm-app": "crm",
    "sales": "crm",
    "mobile-app": "mobile",
    "expo": "mobile",
    "react-native": "mobile",
    "rn": "mobile",
}

VALID_RRI_PERSONAS: tuple[str, ...] = ("end_user", "ba", "qa", "developer", "operator")
VALID_RRI_MODES: tuple[str, ...] = ("CHALLENGE", "GUIDED", "EXPLORE")


def _resolve_rri_project_type(project_type: str) -> str:
    if not project_type:
        return "custom"
    key = project_type.strip().lower().replace("_", "-")
    return _RRI_PROJECT_ALIASES.get(key, key)


def load_rri_questions(
    project_type: str,
    persona: str | None = None,
    mode: str | None = None,
) -> list[dict[str, str]]:
    """Return the canonical RRI question list for a project type.

    Project types: landing, saas, dashboard, blog, docs, portfolio,
    ecommerce, enterprise-module, api, crm, mobile, custom.

    v0.11.2 (FIX-003) extends the signature with optional ``persona``
    (one of ``VALID_RRI_PERSONAS``) and ``mode`` (one of
    ``VALID_RRI_MODES``).  When supplied, results are filtered.
    Unknown / aliased project types fall back to the ``custom`` bank
    so callers always get a non-empty result for safe defaulting.

    Each question is a dict with keys ``id``, ``persona``, ``mode``, ``q``.

    **Language posture (v0.11.4 Obs-2).**  The RRI methodology itself
    is *prompt-language-agnostic*: personas, modes, and question IDs
    are structural and carry no locale.  The shipped question text
    (``q`` field) is **Vietnamese-first** — it matches the product's
    primary audience (VIBECODE-MASTER / RRI-T were designed for
    Vietnamese enterprise software teams).  LLMs consuming these
    questions are expected to:

    1. Render the question to the end user in whatever language the
       user has been speaking (VN / EN / mixed) — translate on the
       fly if needed.
    2. Accept answers in any language and normalise them for the
       downstream planning / verify pipeline.

    Downstream probes (``14_plugin_extension``,
    ``36_methodology_slash_commands``) only check structural fields
    (``id``, ``persona``, ``mode``) and do not assert on the prose
    locale, so translators / forks are free to localise ``q`` without
    breaking the audit.
    """
    if persona is not None and persona not in VALID_RRI_PERSONAS:
        raise ValueError(f"unknown persona {persona!r}; " f"known: {list(VALID_RRI_PERSONAS)}")
    if mode is not None and mode not in VALID_RRI_MODES:
        raise ValueError(f"unknown mode {mode!r}; " f"known: {list(VALID_RRI_MODES)}")
    path = _question_bank_path()
    if not path.exists():
        raise FileNotFoundError(f"question bank not bundled: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    types = data.get("project_types", {})
    canonical = _resolve_rri_project_type(project_type)
    if canonical not in types and "custom" in types:
        canonical = "custom"
    if canonical not in types:
        raise ValueError(f"unknown project_type {project_type!r}; " f"known: {sorted(types)}")
    questions = list(types[canonical].get("questions", []))
    if persona is not None:
        questions = [q for q in questions if q.get("persona") == persona]
    if mode is not None:
        questions = [q for q in questions if q.get("mode") == mode]
    return questions


def list_rri_question_project_types() -> list[str]:
    path = _question_bank_path()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return sorted(data.get("project_types", {}).keys())


# ---------------------------------------------------------------------------
# Stack recommendations (v0.11.2 / FIX-002, port of master v5 §A)
# ---------------------------------------------------------------------------

PROJECT_STACK_RECOMMENDATIONS: dict[str, dict[str, Any]] = {
    "landing": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind CSS",
        "state_data": "—",
        "auth": "—",
        "hosting": "Vercel",
        "extras": ["Framer Motion", "next/font/google", "Resend (lead capture)"],
        "default_scaffold": "landing-page",
        "rationale": "Static, SEO-first, sub-second TTI; serverless email capture only.",
    },
    "saas": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind + shadcn/ui",
        "state_data": "Supabase / Postgres",
        "auth": "NextAuth (or Clerk for B2B)",
        "hosting": "Vercel",
        "extras": ["Prisma", "Stripe", "Resend", "Sentry"],
        "default_scaffold": "saas",
        "rationale": "Multi-tenant Postgres + canonical Next.js auth + payment.",
    },
    "dashboard": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind + shadcn/ui",
        "state_data": "TanStack Query + Postgres / ClickHouse",
        "auth": "NextAuth",
        "hosting": "Vercel",
        "extras": ["Recharts", "ECharts (heavy charts)", "Redis cache"],
        "default_scaffold": "dashboard",
        "rationale": "Read-heavy; cache aggressively; defer heavy charts to client.",
    },
    "blog": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind + Typography plugin",
        "state_data": "MDX (file-system) or Sanity/Contentful",
        "auth": "—",
        "hosting": "Vercel",
        "extras": ["rehype-pretty-code", "RSS feed", "OG image route"],
        "default_scaffold": "blog",
        "rationale": "MDX wins on developer ergonomics; CMS only when multi-author.",
    },
    "docs": {
        "framework": "Next.js + Nextra",
        "styling": "Tailwind",
        "state_data": "MDX (file-system)",
        "auth": "—",
        "hosting": "Vercel",
        "extras": ["Algolia DocSearch", "i18n vi/en", "versioned navigation"],
        "default_scaffold": "docs",
        "rationale": "Sidebar + ToC + search out of the box; i18n included.",
    },
    "portfolio": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind",
        "state_data": "MDX (file-system)",
        "auth": "—",
        "hosting": "Vercel",
        "extras": ["Framer Motion", "next/image", "Resend (contact form)"],
        "default_scaffold": "portfolio",
        "rationale": "Editorial + motion; image optimisation matters more than CMS.",
    },
    "ecommerce": {
        "framework": "Next.js (App Router)",
        "styling": "Tailwind + shadcn/ui",
        "state_data": "Supabase / Postgres",
        "auth": "NextAuth",
        "hosting": "Vercel",
        "extras": ["Stripe Checkout", "VNPay/MoMo (VN market)", "Algolia search", "Cloudinary CDN"],
        "default_scaffold": "shop-online",
        "rationale": "Cart-state must persist; tax/shipping zones drive schema.",
    },
    "mobile": {
        "framework": "Expo (React Native)",
        "styling": "NativeWind (Tailwind for RN)",
        "state_data": "TanStack Query + Supabase",
        "auth": "Supabase Auth (or Clerk Expo SDK)",
        "hosting": "EAS Build + EAS Submit",
        "extras": ["Expo Router", "Sentry RN", "OneSignal push"],
        "default_scaffold": "mobile-app",
        "rationale": "Expo > bare RN for time-to-store; EAS handles iOS/Android builds.",
    },
    "api": {
        "framework": "FastAPI (Python) — or Hono (TypeScript)",
        "styling": "—",
        "state_data": "Postgres + SQLAlchemy / Drizzle",
        "auth": "JWT + OAuth2 / Clerk",
        "hosting": "Fly.io / Railway / Cloudflare Workers (Hono)",
        "extras": ["pydantic v2", "Alembic migrations", "OpenAPI auto-docs"],
        "default_scaffold": "api-todo",
        "rationale": "Pick FastAPI for ML-adjacent / Python infra; Hono for edge.",
    },
    "enterprise-module": {
        "framework": "Reuse from Scan",
        "styling": "Reuse from Scan",
        "state_data": "Reuse from Scan",
        "auth": "Reuse from Scan",
        "hosting": "Reuse from Scan",
        "extras": ["Only NEW capability surfaces of this module"],
        "default_scaffold": None,
        "rationale": "Pattern F: never introduce a new stack inside an existing codebase.",
    },
    "custom": {
        "framework": "Choose explicitly with Homeowner",
        "styling": "Choose explicitly with Homeowner",
        "state_data": "Choose explicitly with Homeowner",
        "auth": "Choose explicitly with Homeowner",
        "hosting": "Choose explicitly with Homeowner",
        "extras": [],
        "default_scaffold": None,
        "rationale": "Custom = explicit decision required; Vision must spell out every cell.",
    },
}


def recommend_stack(project_type: str) -> dict[str, Any]:
    """Return the canonical stack recommendation for a project type.

    Always returns a dict — unknown / aliased / empty inputs fall back to
    the ``custom`` row (safe default: forces explicit choice).
    """
    if not project_type:
        out = dict(PROJECT_STACK_RECOMMENDATIONS["custom"])
        out["resolved_from"] = ""
        out["unknown"] = True
        return out
    key = project_type.strip().lower().replace("_", "-")
    aliases = {
        "landing-page": "landing",
        "marketing": "landing",
        "saas-app": "saas",
        "saas-product": "saas",
        "admin": "dashboard",
        "analytics": "dashboard",
        "blog-site": "blog",
        "writing": "blog",
        "docs-site": "docs",
        "documentation": "docs",
        "knowledge-base": "docs",
        "personal": "portfolio",
        "showcase": "portfolio",
        "shop": "ecommerce",
        "shop-online": "ecommerce",
        "store": "ecommerce",
        "expo": "mobile",
        "react-native": "mobile",
        "rn": "mobile",
        "rest-api": "api",
        "graphql": "api",
        "backend": "api",
        "module": "enterprise-module",
        "feature": "enterprise-module",
        "enterprise": "enterprise-module",
    }
    canonical = aliases.get(key, key)
    if canonical not in PROJECT_STACK_RECOMMENDATIONS:
        # Unknown → safe fallback: the custom row.
        out = dict(PROJECT_STACK_RECOMMENDATIONS["custom"])
        out["resolved_from"] = project_type
        out["unknown"] = True
        return out
    out = dict(PROJECT_STACK_RECOMMENDATIONS[canonical])
    out["resolved_from"] = canonical
    out["unknown"] = False
    return out


def list_stack_recommendations() -> list[str]:
    return sorted(PROJECT_STACK_RECOMMENDATIONS.keys())


# ---------------------------------------------------------------------------
# v0.11.3 / Patch A — Reference loader + per-command context composer
# ---------------------------------------------------------------------------
#
# Closes deep-dive cycle finding W1 ("references not wired into runtime").
# Until v0.11.2 the 35 reference markdown files in ``references/`` were
# documentation — only ``conformance_audit`` ever read them.  The slash
# commands and agents lacked any helper for pulling reference bodies (or
# specific sections) into an LLM prompt.
#
# These helpers turn the references into a runtime knowledge base that
# slash commands can compose with dynamic data (``recommend_stack``,
# ``load_rri_questions``) into a single context block.

_REF_FILENAME_PATTERN = re.compile(r"^(\d{2})-([\w\-]+)\.md$")


def _references_root() -> Path:
    """Resolve the ``references/`` directory across known layouts."""
    env = os.environ.get("VIBECODE_SKILL_ROOT")
    if env:
        cand = Path(env) / "references"
        if cand.exists():
            return cand
    here = Path(__file__).resolve()
    # scripts/vibecodekit/methodology.py → parents[2] = skill bundle root
    skill_root = here.parents[2]
    return skill_root / "references"


def list_references() -> list[dict[str, str]]:
    """Return ``[{ref_id, filename, title}, …]`` for every reference."""
    root = _references_root()
    out: list[dict[str, str]] = []
    if not root.exists():
        return out
    for p in sorted(root.glob("*.md")):
        m = _REF_FILENAME_PATTERN.match(p.name)
        if not m:
            continue
        ref_id = f"ref-{m.group(1)}"
        title = ""
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        out.append({"ref_id": ref_id, "filename": p.name, "title": title})
    return out


def load_reference(ref_id: str) -> str:
    """Return the full body of ``references/NN-*.md`` for ``ref_id="ref-NN"``.

    Raises :class:`FileNotFoundError` if no reference matches.  Both
    ``ref-34`` and ``34`` are accepted.
    """
    if not ref_id:
        raise ValueError("ref_id must be non-empty")
    digits = re.sub(r"[^0-9]", "", str(ref_id))
    if len(digits) < 2:
        raise ValueError(f"ref_id must contain a 2-digit index, got {ref_id!r}")
    prefix = digits[:2]
    root = _references_root()
    matches = sorted(root.glob(f"{prefix}-*.md")) if root.exists() else []
    if not matches:
        raise FileNotFoundError(f"reference {ref_id!r} not found under {root}")
    return matches[0].read_text(encoding="utf-8")


def load_reference_section(ref_id: str, heading: str) -> str:
    """Return the body of one ``## …`` / ``### …`` section from a reference.

    ``heading`` is matched case-insensitively and ignores leading "#" /
    whitespace.  The section body is everything from the matched heading
    line (inclusive) up to the next heading of equal-or-shallower depth.
    """
    body = load_reference(ref_id)
    target = heading.strip().lstrip("#").strip().lower()
    if not target:
        raise ValueError("heading must be non-empty")
    lines = body.splitlines()
    start: int | None = None
    start_depth = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            continue
        # Count leading hashes
        depth = len(line) - len(line.lstrip("#"))
        text = line[depth:].strip().lower()
        if text == target or text.startswith(target + " ") or text.startswith(target + ":"):
            start = i
            start_depth = depth
            break
    if start is None:
        raise LookupError(f"section {heading!r} not found in {ref_id}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("#"):
            d = len(lines[j]) - len(lines[j].lstrip("#"))
            if d <= start_depth:
                end = j
                break
    return "\n".join(lines[start:end]).rstrip() + "\n"


# Per-slash-command wiring map.
#
# Each entry lists the ``ref-NN`` IDs whose body should be injected
# verbatim, plus optional dynamic-data hooks that fill in
# project-type-specific content.  ``render_command_context`` walks this
# map and produces a single string suitable for prepending to a slash
# command's prompt.
COMMAND_REFERENCE_WIRING: dict[str, dict[str, Any]] = {
    "vibe-vision": {
        "refs": ["ref-30", "ref-34"],
        "dynamic": ("recommend_stack", "ref-36-headlines"),
    },
    "vibe-rri": {
        "refs": ["ref-21", "ref-29"],
        "dynamic": ("rri-questions",),
    },
    "vibe-rri-ui": {
        "refs": ["ref-22", "ref-33", "ref-34"],
        "dynamic": (),
    },
    "vibe-rri-ux": {
        "refs": ["ref-22", "ref-32"],
        "dynamic": (),
    },
    "vibe-rri-t": {
        "refs": ["ref-31"],
        "dynamic": (),
    },
    "vibe-blueprint": {
        "refs": ["ref-30"],
        "dynamic": (),
    },
    "vibe-verify": {
        "refs": ["ref-25", "ref-26"],
        "dynamic": (),
    },
    "vibe-refine": {
        "refs": ["ref-30", "ref-36"],
        "dynamic": (),
    },
    "vibe-audit": {
        "refs": ["ref-25", "ref-26", "ref-32"],
        "dynamic": (),
    },
    "vibe-module": {
        "refs": ["ref-35"],
        "dynamic": (),
    },
    "vibe-scaffold": {
        "refs": ["ref-34"],
        "dynamic": ("recommend_stack",),
    },
}


def list_wired_commands() -> list[str]:
    return sorted(COMMAND_REFERENCE_WIRING.keys())


def render_command_context(
    command: str,
    *,
    project_type: str | None = None,
    persona: str | None = None,
    mode: str | None = None,
    max_questions: int = 12,
) -> str:
    """Compose an LLM-ready context block for a slash command.

    The block contains:

    * One ``## Reference: <ref-id> — <title>`` section per wired
      reference, with the full body inlined.
    * One ``## Dynamic: stack recommendation`` block when
      ``project_type`` is provided and the command pulls
      ``recommend_stack``.
    * One ``## Dynamic: RRI question subset`` block when the command
      pulls ``rri-questions`` (filtered by ``persona`` / ``mode`` when
      given, capped at ``max_questions`` to keep prompts bounded).

    Unknown commands return an empty string instead of raising — the
    caller can defensively wrap any slash command without needing to
    know the wiring map.
    """
    wiring = COMMAND_REFERENCE_WIRING.get(command)
    if not wiring:
        return ""
    parts: list[str] = []
    parts.append(f"# Wired context for /{command}\n")
    for ref_id in wiring.get("refs", []):
        try:
            body = load_reference(ref_id)
        except FileNotFoundError:
            continue
        # Strip the leading H1 to avoid duplicate headings.
        lines = body.splitlines()
        title = ""
        body_lines = lines
        if lines and lines[0].startswith("# "):
            title = lines[0][2:].strip()
            body_lines = lines[1:]
        heading = f"## Reference: {ref_id}"
        if title:
            heading += f" — {title}"
        parts.append(heading + "\n")
        parts.append("\n".join(body_lines).strip() + "\n")
    dynamic = wiring.get("dynamic", ())
    if "recommend_stack" in dynamic and project_type:
        try:
            rec = recommend_stack(project_type)
        except Exception:  # noqa: BLE001
            rec = None
        if rec:
            parts.append("## Dynamic: stack recommendation\n")
            parts.append(
                f"- project_type: {project_type}\n"
                f"- resolved_from: {rec.get('resolved_from')}\n"
                f"- unknown_fallback: {rec.get('unknown')}\n"
                f"- framework: {rec.get('framework')}\n"
                f"- styling: {rec.get('styling')}\n"
                f"- state_data: {rec.get('state_data')}\n"
                f"- auth: {rec.get('auth')}\n"
                f"- hosting: {rec.get('hosting')}\n"
                f"- extras: {', '.join(rec.get('extras', [])) or '—'}\n"
                f"- default_scaffold: {rec.get('default_scaffold')}\n"
            )
    if "rri-questions" in dynamic and project_type:
        try:
            qs = load_rri_questions(project_type, persona, mode)
        except (ValueError, FileNotFoundError):
            qs = []
        qs = qs[: max(0, int(max_questions))]
        if qs:
            parts.append("## Dynamic: RRI question subset\n")
            parts.append(
                f"_filtered_ project_type={project_type} persona={persona or '*'} "
                f"mode={mode or '*'} limit={max_questions}\n"
            )
            for q in qs:
                parts.append(f"- **{q['id']}** [{q['persona']}/{q['mode']}]: {q['q']}\n")
    return "\n".join(parts).rstrip() + "\n"
