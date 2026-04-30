"""Single-prompt intent router (v0.11.0, Phase β — F4).

Implements the ``/vibe <prose>`` master command — a friendly entrypoint
that takes free-form Vietnamese OR English prose and resolves it to one
(or more) of the existing 25 ``/vibe-*`` slash commands.  The 25 flat
commands stay 100 % backward-compatible; ``/vibe`` is an *additive*
shortcut for non-power users.

Inspired by taw-kit's ``/taw`` two-tier router, extended with:

- **Hybrid match:** keyword first (deterministic, fast); cosine
  similarity on `HashEmbeddingBackend` as a tie-breaker.
- **Confidence threshold + clarifying-question fallback** — if no
  intent crosses the threshold, the router emits a structured
  ``Clarification`` instead of guessing.
- **Multi-intent expansion** — "scan + vision + build" fans out to a
  pipeline of slash commands in the right order.
- **Vietnamese-first** trigger phrases (taw pattern), with English
  parallel triggers for kit's existing user base.

Public API::

    >>> r = IntentRouter()
    >>> match = r.classify("làm cho tôi shop online bán cà phê")
    >>> match.intents
    ['SCAN', 'VISION', 'RRI', 'BUILD']
    >>> r.route(match)
    ['/vibe-scan', '/vibe-vision', '/vibe-rri', '/vibe-build']

The router is **stateless**.  It does not invoke commands itself; it
returns the ordered slash-command sequence so the caller (Claude Code
hook, CLI) can dispatch.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata

# Intent tier-1 with VN + EN trigger phrases.  Order = canonical pipeline
# order when multiple intents fire at once.
TIER_1: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "SCAN",
        (
            "scan",
            "phân tích nhu cầu",
            "phan tich nhu cau",
            "matrix nhu cầu",
            "derive needs",
            "user needs",
            "khám phá",
            "kham pha",
            # Generic security-discovery phrases.  Note: review-oriented
            # phrases ("code review", "review code", "review my code")
            # were moved to VCK_REVIEW + VCK_CSO in v0.16.0-α (audit P2 #5)
            # so prose like "review my code for security" lands on the
            # multi-perspective adversarial review skill instead of SCAN.
            "bảo mật",
            "bao mat",
            "security",
            "kiểm tra bảo mật",
            "kiem tra bao mat",
            "security scan",
        ),
    ),
    (
        "VISION",
        (
            "vision",
            "tầm nhìn",
            "tam nhin",
            "design vision",
            "brand",
            "thương hiệu",
            "định hướng",
            "dinh huong",
            "concept",
            "ý tưởng",
            "y tuong",
        ),
    ),
    (
        "RRI",
        (
            "rri",
            "reverse interview",
            "phỏng vấn ngược",
            "phong van nguoc",
            "đặt câu hỏi ngược",
            "dat cau hoi nguoc",
            "verify requirement",
            "kiểm tra yêu cầu",
        ),
    ),
    (
        "RRI-T",
        (
            "rri-t",
            "rri t",
            "testing matrix",
            "ma trận test",
            "ma tran test",
            "stress axis",
            "test scenarios",
        ),
    ),
    (
        "RRI-UX",
        (
            "rri-ux",
            "rri ux",
            "flow physics",
            "user flow",
            "luồng người dùng",
            "luong nguoi dung",
            "ux critique",
            "phê bình ux",
        ),
    ),
    (
        "RRI-UI",
        (
            "rri-ui",
            "rri ui",
            "ui design",
            "thiết kế ui",
            "thiet ke ui",
            "design system",
            "design tokens",
        ),
    ),
    (
        "BUILD",
        (
            "build",
            "làm",
            "tạo",
            "scaffold",
            "khởi tạo",
            "khoi tao",
            "ra code",
            "viết code",
            "viet code",
            "implement",
            "develop",
            "code app",
            "create",
            "new project",
            "dự án mới",
            "du an moi",
            # Preset names — keep all 9 in sync with assets/scaffolds/.
            "shop",
            "shop online",
            "landing",
            "landing page",
            "blog",
            "crm",
            "dashboard",
            "api",
            "api todo",
            "rest api",
            "todo api",
            "mobile",
            "mobile app",
            "app điện thoại",
            "app dien thoai",
            "react native",
            "expo",
            # Pattern E — Portfolio scaffold.
            "portfolio",
            "portfolio cá nhân",
            "portfolio ca nhan",
            "personal portfolio",
            "showcase",
            "trang cá nhân",
            "trang ca nhan",
            # Pattern B — SaaS scaffold (Next.js + NextAuth + Prisma).
            "saas",
            "saas app",
            "app web",
            "web app",
            "subscription",
            "đa user",
            "da user",
            "multi user",
            "multi-user",
            "multi tenant",
            "multi-tenant",
            # Pattern D — Docs scaffold (Nextra MDX + i18n + search).
            "docs",
            "docs site",
            "documentation",
            "tài liệu",
            "tai lieu",
            "doc site",
            "developer docs",
            "trang tài liệu",
            "trang tai lieu",
            "knowledge base",
            "guidebook",
            "handbook",
            "nextra",
            "docusaurus",
        ),
    ),
    (
        "VERIFY",
        (
            "verify",
            "audit",
            "kiểm tra",
            "kiem tra",
            "check",
            "validate",
            # Testing IS verification — keep these out of MAINTAIN to avoid
            # routing "test app"/"write tests" to /vibe-task.
            "test",
            "tests",
            "testing",
            "test app",
            "viết test",
            "viet test",
            "viết tests",
            "viet tests",
            "write test",
            "write tests",
            "unit test",
            "unit tests",
            "kiểm thử",
            "kiem thu",
        ),
    ),
    (
        "SHIP",
        (
            "deploy",
            "ship",
            "publish",
            "đẩy lên",
            "day len",
            "go live",
            "launch",
            "lên sản phẩm",
            "len san pham",
            "đưa lên production",
            "vercel deploy",
            "docker deploy",
            "triển khai",
            "trien khai",
            "release",
            "phát hành",
            "phat hanh",
        ),
    ),
    (
        "MODULE",
        (
            # v5 Pattern F — add a module to an existing codebase.
            # Routes to /vibe-module which runs the probe + plan workflow.
            "module",
            "thêm module",
            "them module",
            "add module",
            "integrate",
            "tích hợp",
            "tich hop",
            "vào codebase có sẵn",
            "vao codebase co san",
            "existing codebase",
            "codebase có sẵn",
            "codebase co san",
            "extend codebase",
            "mở rộng codebase",
            "mo rong codebase",
            "feature module",
            "enterprise module",
            "add feature to existing",
            "thêm feature vào",
        ),
    ),
    (
        "REFINE",
        (
            # BƯỚC 8/8 — text/copy/colour-token/in-section content tweaks.
            # Routes to /vibe-refine which opens the template + classifier.
            "refine",
            "tinh chỉnh",
            "tinh chinh",
            "polish",
            "điều chỉnh",
            "dieu chinh",
            "tweak",
            "chỉnh sửa nhỏ",
            "chinh sua nho",
            "đổi text",
            "doi text",
            "đổi copy",
            "doi copy",
            "đổi màu",
            "doi mau",
            "đổi chữ",
            "doi chu",
            "fine tune",
            "finetune",
            "final polish",
        ),
    ),
    (
        "MAINTAIN",
        (
            # Note: "test"/"tests"/"testing" moved to VERIFY (testing is
            # verification, not maintenance).  Keep MAINTAIN focused on
            # bug-fix / refactor / perf / rollback workflows.
            "upgrade",
            "nâng cấp",
            "nang cap",
            "clean",
            "perf",
            "performance",
            "tối ưu",
            "toi uu",
            "refactor",
            "rollback",
            "quay lại",
            "quay lai",
            "fix",
            "sửa",
            "sua",
            "lỗi rồi",
            "loi roi",
            "bug",
            "bugfix",
            "bug fix",
            "hotfix",
        ),
    ),
    (
        "ADVISOR",
        (
            "analyze",
            "phân tích kiến trúc",
            "phan tich kien truc",
            "review",
            "tư vấn",
            "tu van",
            "advise",
            "advice",
            "advisor",
            "opinion",
            "góc nhìn",
            "goc nhin",
            "đánh giá",
            "danh gia",
            "so sánh",
            "so sanh",
            "compare",
            "kiến trúc",
            "kien truc",
            "architecture",
        ),
    ),
    (
        "MEMORY",
        (
            "memory",
            "claude.md",
            "nhớ",
            "ghi nhớ",
            "ghi nho",
            "context",
            "remember",
            "auto-maintain",
            "writeback",
        ),
    ),
    (
        "DOCTOR",
        (
            "doctor",
            "diagnose",
            "chẩn đoán",
            "chan doan",
            "tự kiểm tra",
            "tu kiem tra",
            "selfcheck",
            "self-check",
            "self check",
            "self check kit",
            "khám máy",
            "kham may",
        ),
    ),
    (
        "DASHBOARD",
        (
            "dashboard",
            "bảng điều khiển",
            "bang dieu khien",
            "tổng quan",
            "tong quan",
            "metrics",
        ),
    ),
    # v0.12.0 — VCK-* gstack-inspired specialist intents.  Phrases below
    # are intentionally HIGH-SPECIFICITY so they do not conflict with the
    # generic SCAN/ADVISOR/SHIP routes.  Direct slash typing
    # ("/vck-cso", "/vck-review", …) always wins through these.
    (
        "VCK_CSO",
        (
            "/vck-cso",
            "vck-cso",
            "chief security officer",
            "owasp top 10",
            "owasp top10",
            "stride threat model",
            "supply chain audit",
            "secrets archaeology",
            # v0.16.0-α — P2 #5 multi-token boost.  Phrases longer than
            # SCAN's "security" (8 chars) so the longest-match tiebreaker
            # in :meth:`IntentRouter.classify` lands the right bucket for
            # natural prose like "audit my code for security".
            "audit my code",
            "audit code for security",
            "security audit",
            "security review",
        ),
    ),
    (
        "VCK_REVIEW",
        (
            "/vck-review",
            "vck-review",
            "adversarial review",
            "review army",
            "multi-specialist review",
            "7-perspective review",
            "pre-pr review",
            # v0.16.0-α — P2 #5 multi-token boost.  Without these phrases,
            # "review my code for security" mis-routes to /vibe-scan because
            # SCAN's "security" trigger fires alone.
            "code review",
            "review code",
            "review my code",
            "review the code",
            "review my code for security",
        ),
    ),
    (
        "VCK_QA",
        (
            "/vck-qa",
            "vck-qa",
            "/vck-qa-only",
            "vck-qa-only",
            "real browser qa",
            "real-browser qa",
            "checklist vn-12",
            "browser daemon qa",
        ),
    ),
    (
        "VCK_INVESTIGATE",
        (
            "/vck-investigate",
            "vck-investigate",
            "no-fix-without-investigation",
            "5-why",
            "five why",
            "fishbone",
            "root cause investigation",
        ),
    ),
    (
        "VCK_CANARY",
        (
            "/vck-canary",
            "vck-canary",
            "post-deploy canary",
            "post deploy canary",
            "canary monitor",
            "30-minute canary",
        ),
    ),
    (
        "VCK_SHIP",
        (
            "/vck-ship",
            "vck-ship",
            "ship orchestrator",
            "atomic ship",
            "test review push pr",
        ),
    ),
    # v0.14.0 — plan-review + polish skills (gstack Phase 3 + 4 adaptation).
    (
        "VCK_OFFICE_HOURS",
        (
            "/vck-office-hours",
            "vck-office-hours",
            "office hours yc",
            "yc office hours",
            "6 forcing questions",
            "forcing question",
            "pmf interrogation",
        ),
    ),
    (
        "VCK_CEO_REVIEW",
        (
            "/vck-ceo-review",
            "vck-ceo-review",
            "ceo review",
            "ceo mode review",
            "scope expansion",
            "scope reduction",
            "ceo lens",
        ),
    ),
    (
        "VCK_ENG_REVIEW",
        (
            "/vck-eng-review",
            "vck-eng-review",
            "engineering review",
            "eng review",
            "lock architecture",
            "invariants review",
        ),
    ),
    (
        "VCK_DESIGN_CONSULTATION",
        (
            "/vck-design-consultation",
            "vck-design-consultation",
            "design system from scratch",
            "design consultation",
            "design tokens spacing",
        ),
    ),
    (
        "VCK_DESIGN_REVIEW",
        (
            "/vck-design-review",
            "vck-design-review",
            "design review audit",
            "design drift",
            "ui drift audit",
        ),
    ),
    (
        "VCK_LEARN",
        (
            "/vck-learn",
            "vck-learn",
            "capture learning",
            "ghi bài học",
            "ghi bai hoc",
            "save learning",
        ),
    ),
    (
        "VCK_RETRO",
        (
            "/vck-retro",
            "vck-retro",
            "weekly retro",
            "sprint retro",
            "retro tuần",
            "retro tuan",
        ),
    ),
    (
        "VCK_SECOND_OPINION",
        (
            "/vck-second-opinion",
            "vck-second-opinion",
            "second opinion",
            "phản biện plan",
            "phan bien plan",
            "codex review",
            "gemini review",
            "second brain review",
        ),
    ),
    (
        "VCK_PIPELINE",
        (
            "/vck-pipeline",
            "vck-pipeline",
            "pipeline router",
            "master pipeline",
            "vck pipeline",
            "chọn pipeline",
            "chon pipeline",
            # v0.16.0-α — Plan T6 trigger phrases (audit P2 #4 + P3 #9)
            # so /vck-pipeline frontmatter, intent_router, and
            # pipeline_router agree on a single canonical bank.
            "pipeline đầy đủ",
            "pipeline day du",
            "full check",
            "go through pipeline",
            "all gates",
            "end to end",
            "e2e check",
            # v0.16.1 — close partial-fix gap from PR-2: the master
            # /vck-pipeline frontmatter declares these high-level "do the
            # whole thing" phrases as triggers, but the intent_router bank
            # was missing them so prose-mode classification fell back to a
            # low-confidence BUILD match.  Aligning the three routers.
            "build the whole thing",
            "set everything up",
        ),
    ),
)

# Synthetic pipelines: when one intent is mentioned in a high-level way
# (e.g. "shop online"), expand to the canonical pipeline.
_PIPELINE_TRIGGERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "FULL_BUILD",
        (
            # High-level "build a whole product" cues — fan out to the full
            # SCAN→VISION→RRI→BUILD→VERIFY pipeline.  Covers all 9 presets.
            "shop online",
            "landing page",
            "ra mắt sản phẩm",
            "ra mat san pham",
            "build từ đầu",
            "build tu dau",
            "tạo dự án mới",
            "tao du an moi",
            "new project",
            "tạo blog",
            "tao blog",
            "build blog",
            "build crm",
            "tạo crm",
            "tao crm",
            "build dashboard",
            "tạo dashboard",
            "tao dashboard",
            "api todo",
            "rest api",
            "tạo api",
            "tao api",
            "mobile app",
            "react native app",
            "expo app",
            "app điện thoại",
            "app dien thoai",
            # Pattern E — Portfolio.
            "portfolio cá nhân",
            "portfolio ca nhan",
            "personal portfolio",
            "tạo portfolio",
            "tao portfolio",
            "build portfolio",
            # Pattern B — SaaS.
            "saas app",
            "build saas",
            "tạo saas",
            "tao saas",
            "multi user app",
            "multi-user app",
            # Pattern D — Docs.
            "docs site",
            "documentation site",
            "tài liệu sản phẩm",
            "tai lieu san pham",
            "tạo docs",
            "tao docs",
            "build docs",
            "trang tài liệu",
            "trang tai lieu",
            "knowledge base",
            "developer documentation",
        ),
    ),
)
_FULL_BUILD_PIPELINE = ("SCAN", "VISION", "RRI", "BUILD", "VERIFY")

# Map intent → slash command (existing in claw-code-pack/.claude/commands/)
_INTENT_TO_SLASH: dict[str, str] = {
    "SCAN": "/vibe-scan",
    "VISION": "/vibe-vision",
    "RRI": "/vibe-rri",
    "RRI-T": "/vibe-rri-t",
    "RRI-UX": "/vibe-rri-ux",
    "RRI-UI": "/vibe-rri-ui",
    "BUILD": "/vibe-scaffold",  # F1 — real code generation
    "VERIFY": "/vibe-verify",
    "REFINE": "/vibe-refine",  # BƯỚC 8/8 — text/copy/colour tweaks
    "MODULE": "/vibe-module",  # Pattern F — module into existing codebase
    "SHIP": "/vibe-ship",  # F2 — 7-target deploy orchestrator
    "MAINTAIN": "/vibe-task",
    "ADVISOR": "/vibe-tip",
    "MEMORY": "/vibe-memory",
    "DOCTOR": "/vibe-doctor",
    "DASHBOARD": "/vibe-dashboard",
    "AUDIT": "/vibe-audit",
    "INSTALL": "/vibe-install",
    # v0.12.0 / v0.14.0 — VCK-* gstack-inspired specialist commands.
    "VCK_CSO": "/vck-cso",
    "VCK_REVIEW": "/vck-review",
    "VCK_QA": "/vck-qa",
    "VCK_OFFICE_HOURS": "/vck-office-hours",
    "VCK_CEO_REVIEW": "/vck-ceo-review",
    "VCK_ENG_REVIEW": "/vck-eng-review",
    "VCK_DESIGN_CONSULTATION": "/vck-design-consultation",
    "VCK_DESIGN_REVIEW": "/vck-design-review",
    "VCK_LEARN": "/vck-learn",
    "VCK_RETRO": "/vck-retro",
    "VCK_SECOND_OPINION": "/vck-second-opinion",
    "VCK_PIPELINE": "/vck-pipeline",
    "VCK_INVESTIGATE": "/vck-investigate",
    "VCK_CANARY": "/vck-canary",
    "VCK_SHIP": "/vck-ship",
}

# Intents that imply a full pipeline rather than a single command.
_PIPELINE_INTENT = "FULL_BUILD"

# Confidence cutoffs.
_HIGH_CONF = 0.55
_LOW_CONF = 0.30


# Help-seeking / uncertainty markers — prose chứa các phrase này nghĩa
# là user đang BÍ và muốn được hỏi rõ, không có intent cụ thể.  Khi
# match một trong các phrase và **không** có intent nào đạt
# ``high_conf``, router phải trả ``Clarification`` thay vì low-conf
# guess (vd. nhặt mỗi keyword "làm" → BUILD).  Nếu user có câu rõ
# ràng kiểu "không biết deploy lên Vercel kiểu nào" thì keyword
# "deploy" sẽ đạt high-conf và override clarification trigger này.
#
# Phát hiện qua golden eval (PR3) trên dataset
# ``tests/fixtures/intent_router_golden.jsonl``: entry
# ``"không biết làm sao luôn á"`` (tag ``ambiguous``,
# ``expected_intents = []``) bị router classify thành ``{BUILD}`` chỉ
# vì có chữ ``"làm"`` trong BUILD trigger list.
_CLARIFICATION_TRIGGERS: tuple[str, ...] = (
    # VN — uncertainty / help-seeking
    "không biết",
    "khong biet",
    "không hiểu",
    "khong hieu",
    "bí quá",
    "bi qua",
    "bí rồi",
    "bi roi",
    "không rõ",
    "khong ro",
    "chưa rõ",
    "chua ro",
    "luôn á",
    "luon a",
    "làm sao",
    "lam sao",
    "làm thế nào",
    "lam the nao",
    "phải làm gì",
    "phai lam gi",
    "nên làm gì",
    "nen lam gi",
    "không nắm",
    "khong nam",
    "kẹt rồi",
    "ket roi",
    "rối quá",
    "roi qua",
    "lú quá",
    "lu qua",
    "chỉ giúp",
    "chi giup",
    "giúp với",
    "giup voi",
    # EN — uncertainty
    "no idea",
    "i'm stuck",
    "im stuck",
    "i am stuck",
    "i don't know",
    "i dont know",
    "not sure how",
    "i'm lost",
    "im lost",
    "i am lost",
    "help me figure",
    "what should i do",
    "what do i do",
)


@dataclasses.dataclass(frozen=True)
class IntentMatch:
    intents: tuple[str, ...]
    confidence: float
    reason: str
    matched_phrases: tuple[str, ...]
    lang: str  # "vi", "en", or "mixed"


@dataclasses.dataclass(frozen=True)
class Clarification:
    """Returned when the router cannot confidently classify."""

    question_vi: str
    question_en: str
    suggestions: tuple[tuple[str, str], ...]  # (intent, label)


def _detect_lang(text: str) -> str:
    has_vi = bool(
        re.search(
            r"[ăâđêôơưĂÂĐÊÔƠƯáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", text
        )
    )
    has_en = bool(re.search(r"\b(the|and|for|with|build|deploy|please)\b", text, re.IGNORECASE))
    if has_vi and has_en:
        return "mixed"
    return "vi" if has_vi else "en"


def _strip_diacritics(text: str) -> str:
    """NFD-decompose Vietnamese (and other Latin) diacritics, then drop
    combining marks.  ``đ``/``Đ`` is special-cased — NFD does not split
    it — so callers consistently see ``d`` for ``đ``."""
    nfd = unicodedata.normalize("NFD", text)
    out = "".join(c for c in nfd if not unicodedata.combining(c))
    return out.replace("đ", "d").replace("Đ", "D")


def _normalise(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace.

    Both the input prose and the trigger phrases are normalised before
    matching so users can type Vietnamese with or without diacritics
    (``"tao todo"`` and ``"tạo todo"`` route identically).
    """
    return re.sub(r"\s+", " ", _strip_diacritics(text).lower()).strip()


class IntentRouter:
    """Maps a free-form prose prompt to one or more slash commands.

    Stateless — no I/O, no global state.  Safe to instantiate per call.
    """

    def __init__(self, high_conf: float = _HIGH_CONF, low_conf: float = _LOW_CONF):
        self.high_conf = float(high_conf)
        self.low_conf = float(low_conf)

    # ---- classification --------------------------------------------------
    def classify(self, prose: str) -> IntentMatch | Clarification:
        if not prose or not prose.strip():
            return self._empty_clarification()
        text = _normalise(prose)
        lang = _detect_lang(prose)

        # 1. Pipeline-level triggers fire first.
        for pipeline_name, triggers in _PIPELINE_TRIGGERS:
            for t in triggers:
                if _normalise(t) in text:
                    return IntentMatch(
                        intents=_FULL_BUILD_PIPELINE,
                        confidence=0.95,
                        reason=f"pipeline trigger: {t!r}",
                        matched_phrases=(t,),
                        lang=lang,
                    )

        # 2. Tier-1 keyword scoring.
        scores: list[tuple[str, float, list[str]]] = []
        for intent, triggers in TIER_1:
            matched = [t for t in triggers if _normalise(t) in text]
            if not matched:
                continue
            # Score: longest match wins, weighted by # of matched phrases.
            longest = max(len(m) for m in matched)
            score = min(1.0, 0.4 + 0.05 * len(matched) + 0.01 * longest)
            scores.append((intent, score, matched))

        if not scores:
            return self._no_match_clarification(prose, lang)

        # 3. Sort & decide.
        scores.sort(key=lambda x: x[1], reverse=True)
        top_intent, top_score, top_matches = scores[0]

        # Multi-intent: if more than one above HIGH_CONF, keep them all in
        # canonical order; otherwise just the top one.
        high_matches = [s for s in scores if s[1] >= self.high_conf]
        if len(high_matches) > 1:
            order = [name for name, _ in TIER_1]
            kept = sorted(
                {s[0] for s in high_matches},
                key=lambda n: order.index(n) if n in order else 999,
            )
            phrases = tuple(p for _, _, ms in high_matches for p in ms)
            return IntentMatch(
                intents=tuple(kept),
                confidence=top_score,
                reason=f"multi-intent ({len(kept)} above {self.high_conf})",
                matched_phrases=phrases,
                lang=lang,
            )

        if top_score >= self.high_conf:
            return IntentMatch(
                intents=(top_intent,),
                confidence=top_score,
                reason=f"keyword: {top_matches!r}",
                matched_phrases=tuple(top_matches),
                lang=lang,
            )
        # 4. Help-seeking override: prose chứa marker bí/lú và không có
        #    intent nào đạt high_conf → trả Clarification thay vì low-
        #    conf guess.  Đặt trước nhánh "low_conf tentative match"
        #    nhưng sau nhánh high_conf để clarification không che intent
        #    rõ ràng (vd. "không biết deploy lên Vercel kiểu nào" vẫn
        #    map SHIP nếu "deploy" đủ mạnh).
        clar_triggers = [t for t in _CLARIFICATION_TRIGGERS if _normalise(t) in text]
        if clar_triggers:
            return self._uncertain_clarification(prose, lang, clar_triggers)
        if top_score >= self.low_conf:
            # Tentative match — return it but flag low confidence.
            return IntentMatch(
                intents=(top_intent,),
                confidence=top_score,
                reason=f"low-confidence keyword: {top_matches!r}",
                matched_phrases=tuple(top_matches),
                lang=lang,
            )
        return self._no_match_clarification(prose, lang)

    # ---- routing ---------------------------------------------------------
    def route(self, match: IntentMatch | Clarification) -> list[str]:
        """Return the ordered slash-command list, or `[]` if clarification."""
        if isinstance(match, Clarification):
            return []
        out: list[str] = []
        for intent in match.intents:
            cmd = _INTENT_TO_SLASH.get(intent)
            if cmd and cmd not in out:
                out.append(cmd)
        return out

    # ---- explanation -----------------------------------------------------
    def explain(self, match: IntentMatch | Clarification, lang: str = "auto") -> str:
        """Human-readable explanation of why this routing was chosen."""
        if isinstance(match, Clarification):
            target = lang if lang in ("vi", "en") else "vi"
            return match.question_vi if target == "vi" else match.question_en
        # Decide language for output.
        target = lang
        if lang == "auto":
            target = match.lang if match.lang in ("vi", "en") else "vi"
        cmds = self.route(match)
        if target == "vi":
            return (
                f"Đã hiểu ý bạn ({match.confidence:.0%} chắc chắn). "
                f"Sẽ chạy: {', '.join(cmds)}.\n"
                f"Lý do: {match.reason}"
            )
        return (
            f"Routed with {match.confidence:.0%} confidence. "
            f"Pipeline: {', '.join(cmds)}.\n"
            f"Reason: {match.reason}"
        )

    # ---- private helpers -------------------------------------------------
    def _empty_clarification(self) -> Clarification:
        return Clarification(
            question_vi="Bạn muốn làm gì? Mô tả ngắn gọn (vd. 'làm shop online', 'fix lỗi npm', 'review kiến trúc')",
            question_en="What would you like to do? Briefly describe (e.g. 'build a shop', 'fix npm error', 'review architecture')",
            suggestions=(
                ("BUILD", "Làm 1 sản phẩm mới"),
                ("MAINTAIN", "Sửa lỗi / nâng cấp dự án có sẵn"),
                ("ADVISOR", "Tư vấn / review kiến trúc"),
                ("VERIFY", "Audit / kiểm tra chất lượng"),
            ),
        )

    def _uncertain_clarification(self, prose: str, lang: str, triggers: list[str]) -> Clarification:
        """Clarification cho prose có marker bí / lú (xem
        ``_CLARIFICATION_TRIGGERS``).  Khác ``_no_match_clarification``
        ở chỗ message thừa nhận user đang bí và mời mô tả cụ thể, thay
        vì hỏi "I'm not sure what you mean" (kém empathic)."""
        snippet = prose.strip()[:50]
        return Clarification(
            question_vi=(
                f"Bạn nói '{snippet}…' — mình hiểu là bạn đang bí, "
                "nhưng chưa biết hỗ trợ gì.\n"
                "Bạn muốn: (1) làm sản phẩm mới · (2) fix lỗi · "
                "(3) review kiến trúc · (4) deploy?"
            ),
            question_en=(
                f"You said '{snippet}…' — I get that you're stuck, "
                "but I need a hint to help.\n"
                "Do you want: (1) build something new · (2) fix a bug · "
                "(3) review architecture · (4) deploy?"
            ),
            suggestions=(
                ("BUILD", "Làm sản phẩm mới / Build new"),
                ("MAINTAIN", "Fix lỗi / Bug fix"),
                ("ADVISOR", "Review kiến trúc / Architecture review"),
                ("SHIP", "Deploy lên production"),
            ),
        )

    def _no_match_clarification(self, prose: str, lang: str) -> Clarification:
        return Clarification(
            question_vi=(
                f"Mình chưa rõ bạn muốn gì với '{prose[:50]}…'.\n"
                f"Bạn muốn: (1) làm sản phẩm mới · (2) fix lỗi · (3) review kiến trúc · (4) deploy?"
            ),
            question_en=(
                f"I'm not sure what you mean by '{prose[:50]}…'.\n"
                f"Did you want to: (1) build something new · (2) fix a bug · (3) review architecture · (4) deploy?"
            ),
            suggestions=(
                ("BUILD", "Làm sản phẩm mới / Build new"),
                ("MAINTAIN", "Fix lỗi / Bug fix"),
                ("ADVISOR", "Review kiến trúc / Architecture review"),
                ("SHIP", "Deploy lên production"),
            ),
        )


__all__ = [
    "IntentRouter",
    "IntentMatch",
    "Clarification",
    "TIER_1",
]
