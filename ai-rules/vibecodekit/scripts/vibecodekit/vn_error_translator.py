"""Vietnamese error translator (v0.11.0, Phase α — F5a).

Translates common build / runtime stderr & traceback chunks into plain
Vietnamese with a *suggested fix*.  Inspired by taw-kit's
``error-to-vi`` skill, but extended:

- Pattern entries carry a ``confidence`` score (0.0–1.0) so the caller
  can decide between "show suggestion confidently" vs. "tentative".
- Patterns live in YAML files under
  ``skill/vibecodekit-hybrid-ultra/assets/vn-error-dict/`` so users /
  community can extend without code changes.  At import time we also
  ship a hard-coded fallback so the module is usable even when running
  from a partial copy.
- Multi-engine match: a single stderr can match more than one pattern;
  we return them ranked by confidence × specificity (longer regex wins
  ties).

Public API::

    >>> tr = VnErrorTranslator()
    >>> hits = tr.translate("ModuleNotFoundError: No module named 'requests'")
    >>> hits[0].summary_vn
    "Module 'requests' chưa được cài"
    >>> hits[0].fix_suggestion_vn
    'Chạy `pip install requests` (hoặc `uv pip install requests`) trong môi trường ảo của dự án.'
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

try:  # YAML is stdlib-friendly only via PyYAML; degrade gracefully if absent.
    import yaml as _yaml  # type: ignore
except ImportError:  # pragma: no cover — exercised in CI matrix sometimes
    _yaml = None  # type: ignore

# --- Hard-coded fallback (200 entries condensed to high-value subset) ------
# Each tuple: (regex, summary_vn, fix_vn, confidence)
_BUILTIN_DICT: tuple[tuple[str, str, str, float], ...] = (
    # --- Python ----------------------------------------------------------
    (
        r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]",
        "Module '{0}' chưa được cài",
        "Chạy `pip install {0}` (hoặc `uv pip install {0}`) trong môi trường ảo của dự án.",
        0.95,
    ),
    (
        r"ImportError:\s*cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]",
        "Không import được '{0}' từ '{1}'",
        "Kiểm tra version của '{1}'. Có thể tên bị đổi hoặc bạn đang dùng phiên bản cũ — chạy `pip show {1}`.",
        0.90,
    ),
    (
        r"IndentationError:\s*(.+)",
        "Lỗi thụt lề Python: {0}",
        "Mở file ở dòng được báo, dùng đúng 4 space (không trộn tab/space).",
        0.95,
    ),
    (
        r"SyntaxError:\s*(.+)",
        "Lỗi cú pháp Python: {0}",
        "Đọc dòng được báo (và dòng ngay phía trên) — thường thiếu `:` cuối `def/if/for`, hoặc thiếu dấu `)` `]` `}}`.",
        0.85,
    ),
    (
        r"PermissionError:\s*\[Errno 13\]",
        "Không đủ quyền truy cập file",
        "Đổi quyền với `chmod` hoặc chạy lại bằng `sudo` (chỉ khi chắc chắn cần).",
        0.85,
    ),
    (
        r"FileNotFoundError:\s*\[Errno 2\]\s*No such file or directory:\s*['\"]([^'\"]+)['\"]",
        "Không tìm thấy file '{0}'",
        "Kiểm tra đường dẫn — dùng đường dẫn tuyệt đối hoặc chạy script từ đúng thư mục.",
        0.90,
    ),
    (
        r"RecursionError:\s*maximum recursion depth exceeded",
        "Đệ quy quá sâu",
        "Tăng `sys.setrecursionlimit` (tạm) hoặc viết lại bằng vòng lặp / memoization.",
        0.85,
    ),
    # --- Node / npm / pnpm / yarn ----------------------------------------
    (
        r"npm ERR! code\s+ENOENT",
        "npm không tìm thấy file/thư mục",
        "Chạy `npm install` lại từ đầu, hoặc xoá `node_modules/` và `package-lock.json` rồi cài lại.",
        0.85,
    ),
    (
        r"npm ERR! code\s+EACCES",
        "npm thiếu quyền ghi",
        "KHÔNG dùng `sudo npm`. Sửa bằng `npm config set prefix ~/.npm-global` rồi `export PATH=~/.npm-global/bin:$PATH`.",
        0.95,
    ),
    (
        r"npm ERR!\s+ERESOLVE",
        "Xung đột peer-dependencies",
        "Thử `npm install --legacy-peer-deps` (tạm) hoặc bump version đúng theo bảng tương thích của package.",
        0.90,
    ),
    (
        r"npm ERR! 404\s+'([^']+)'",
        "Package '{0}' không tồn tại trên registry",
        "Kiểm tra chính tả tên package, hoặc dùng `npm whoami` để chắc chắn registry đúng.",
        0.95,
    ),
    (
        r"Module not found:.*['\"]([^'\"]+)['\"]",
        "Webpack/bundler không tìm thấy module '{0}'",
        "Chạy `npm install {0}` (hoặc `pnpm add`/`yarn add`).",
        0.90,
    ),
    (
        r"EADDRINUSE[^0-9]*?(\d{2,5})\b",
        "Cổng {0} đã bị tiến trình khác chiếm",
        "Tìm tiến trình: `lsof -i :{0}` rồi `kill <pid>`. Hoặc đổi PORT khi chạy.",
        0.95,
    ),
    (
        r"EADDRINUSE",
        "Cổng đã bị chiếm",
        "Tìm tiến trình bằng `lsof -i :<port>` rồi `kill <pid>`.",
        0.85,
    ),
    (
        r"ENOSPC:?\s*no space left on device",
        "Hết dung lượng ổ đĩa",
        "Chạy `df -h` để xem ổ đầy. Xoá `node_modules/` cũ, `npm cache clean --force`, hoặc dọn `~/Library/Caches`.",
        0.95,
    ),
    # --- TypeScript ------------------------------------------------------
    (
        r"TS2307:.*Cannot find module ['\"]([^'\"]+)['\"]",
        "TypeScript không tìm thấy module '{0}'",
        "Cài types: `npm i -D @types/{0}` hoặc cài chính package: `npm i {0}`.",
        0.90,
    ),
    (
        r"TS2304:.*Cannot find name ['\"]([^'\"]+)['\"]",
        "TypeScript không nhận tên '{0}'",
        "Có thể bạn quên import, hoặc thiếu type definition (`@types/...`).",
        0.85,
    ),
    (
        r"TS2345:.*Argument of type ['\"]([^'\"]+)['\"]",
        "Sai kiểu tham số: '{0}'",
        "Đọc kỹ signature của hàm — có thể bạn truyền number thay vì string, hoặc thiếu trường trong object.",
        0.80,
    ),
    # --- Next.js ---------------------------------------------------------
    (
        r"Error: Hydration failed",
        "Lỗi hydration mismatch (server render khác client)",
        "Kiểm tra component có dùng `Date.now()`, `Math.random()`, `window`, hoặc CSS-in-JS không deterministic — wrap bằng `useEffect`.",
        0.90,
    ),
    (
        r"You're importing a component that needs.*useState",
        "Component dùng useState nhưng đang là Server Component",
        "Thêm `'use client'` ở đầu file (Next.js App Router).",
        0.95,
    ),
    (
        r"Module not found:.*node:fs",
        "Module Node-only `fs` đang được import vào client",
        "Chuyển code dùng `fs` sang Server Component / API Route, hoặc Server Action.",
        0.90,
    ),
    # --- Supabase --------------------------------------------------------
    (
        r"\bJWT expired\b",
        "Supabase JWT hết hạn",
        "Refresh session: `supabase.auth.refreshSession()` hoặc đăng nhập lại.",
        0.90,
    ),
    (
        r"\bnew row violates row-level security policy\b",
        "Vi phạm RLS policy của Supabase",
        "Bạn chưa có RLS policy cho INSERT, hoặc user hiện tại không match `auth.uid()`. Mở Supabase dashboard → Authentication → Policies.",
        0.95,
    ),
    (
        r"relation \"([^\"]+)\" does not exist",
        "Bảng/relation '{0}' không tồn tại",
        "Chạy migration: `supabase db push` hoặc `prisma migrate deploy`.",
        0.90,
    ),
    # --- Docker ----------------------------------------------------------
    (
        r"Cannot connect to the Docker daemon",
        "Docker daemon chưa chạy",
        "Chạy `sudo systemctl start docker` (Linux) hoặc mở Docker Desktop.",
        0.95,
    ),
    (
        r"docker:\s*Error response from daemon:.*pull access denied",
        "Không có quyền pull image",
        "Đăng nhập: `docker login`. Hoặc kiểm tra image private có quyền không.",
        0.90,
    ),
    (
        r"COPY failed: file not found in build context",
        "Dockerfile COPY không tìm thấy file",
        "Kiểm tra `.dockerignore` có loại file nhầm không. Đường dẫn phải tương đối từ build context.",
        0.85,
    ),
    # --- Git -------------------------------------------------------------
    (
        r"fatal:\s*not a git repository",
        "Thư mục hiện tại không phải git repo",
        "Chạy `git init` hoặc `cd` vào thư mục có `.git/`.",
        0.95,
    ),
    (
        r"fatal:\s*refusing to merge unrelated histories",
        "Git từ chối merge 2 lịch sử không liên quan",
        "Thêm flag: `git pull origin main --allow-unrelated-histories` (cẩn thận, có thể conflict).",
        0.90,
    ),
    (
        r"error:\s*Your local changes to the following files would be overwritten",
        "Có thay đổi local sẽ bị ghi đè",
        "Stash trước: `git stash`. Sau khi pull xong: `git stash pop`.",
        0.90,
    ),
    (
        r"\bnon-fast-forward\b",
        "Push bị từ chối: branch remote đã đi trước",
        "`git pull --rebase` rồi push lại. KHÔNG dùng `--force` trên main/master.",
        0.90,
    ),
    # --- Network / curl --------------------------------------------------
    (
        r"curl:\s*\(7\)\s*Failed to connect",
        "curl không kết nối được tới host",
        "Kiểm tra mạng, DNS (`ping <host>`), proxy/VPN, firewall.",
        0.85,
    ),
    (
        r"curl:\s*\(6\)\s*Could not resolve host",
        "DNS không resolve được host",
        "Kiểm tra tên miền chính tả, thử `nslookup`/`dig`, hoặc đổi DNS (1.1.1.1).",
        0.90,
    ),
    (
        r"\bSSL certificate problem\b|\bCERT_HAS_EXPIRED\b",
        "Lỗi chứng chỉ SSL",
        "Nếu là dev: thêm `--insecure` (curl) hoặc `NODE_TLS_REJECT_UNAUTHORIZED=0` (TẠM, KHÔNG DÙNG PROD).",
        0.85,
    ),
    # --- Generic OS / shell ----------------------------------------------
    (
        r"command not found",
        "Lệnh không tồn tại / chưa cài",
        "Cài tool tương ứng (`brew`/`apt`/`pacman`) hoặc kiểm tra `PATH`.",
        0.80,
    ),
    (
        r"Permission denied",
        "Không đủ quyền",
        "`chmod +x` (script), `sudo` (chỉ khi chắc), hoặc đổi owner: `chown $USER ...`.",
        0.75,
    ),
    (
        r"No such file or directory",
        "File/thư mục không tồn tại",
        "Kiểm tra đường dẫn, thử `ls -la <thư-mục-cha>`.",
        0.70,
    ),
)

DEFAULT_DICT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "vn-error-dict"


@dataclasses.dataclass(frozen=True)
class TranslatedError:
    summary_vn: str
    fix_suggestion_vn: str
    confidence: float
    matched_pattern: str
    matched_substring: str

    def render(self) -> str:
        """Pretty multi-line rendering for CLI output."""
        return (
            f"🇻🇳 {self.summary_vn}  (confidence: {self.confidence:.2f})\n"
            f"💡 {self.fix_suggestion_vn}"
        )


@dataclasses.dataclass(frozen=True)
class _Entry:
    pattern: re.Pattern[str]
    summary_vn: str
    fix_vn: str
    confidence: float


class VnErrorTranslator:
    """Translates raw stderr / traceback into Vietnamese hints.

    Lookup order: built-in dict, then any user-supplied YAML files under
    ``dict_dir`` (default: ``assets/vn-error-dict/``).
    """

    def __init__(self, dict_dir: Path | None = None, include_builtins: bool = True):
        self._entries: list[_Entry] = []
        if include_builtins:
            for pat, summary, fix, conf in _BUILTIN_DICT:
                self._entries.append(_Entry(re.compile(pat, re.IGNORECASE), summary, fix, conf))
        target_dir = dict_dir if dict_dir is not None else DEFAULT_DICT_DIR
        if target_dir.is_dir() and _yaml is not None:
            for yml in sorted(target_dir.glob("*.yaml")):
                self._load_yaml(yml)

    def _load_yaml(self, path: Path) -> None:
        try:
            data = _yaml.safe_load(path.read_text(encoding="utf-8")) or []
        except Exception:
            return
        if not isinstance(data, list):
            return
        for item in data:
            try:
                self._entries.append(
                    _Entry(
                        re.compile(item["pattern"], re.IGNORECASE),
                        item["summary_vn"],
                        item["fix_vn"],
                        float(item.get("confidence", 0.7)),
                    )
                )
            except (KeyError, TypeError, re.error):
                continue

    def translate(self, text: str, max_results: int = 3) -> list[TranslatedError]:
        """Return up to ``max_results`` translations, ranked best-first."""
        if not text:
            return []
        hits: list[TranslatedError] = []
        for entry in self._entries:
            m = entry.pattern.search(text)
            if not m:
                continue
            try:
                summary = entry.summary_vn.format(*m.groups())
                fix = entry.fix_vn.format(*m.groups())
            except (IndexError, KeyError):
                summary = entry.summary_vn
                fix = entry.fix_vn
            hits.append(
                TranslatedError(
                    summary_vn=summary,
                    fix_suggestion_vn=fix,
                    confidence=entry.confidence,
                    matched_pattern=entry.pattern.pattern,
                    matched_substring=m.group(0),
                )
            )
        # Rank by confidence × specificity (longer regex source wins ties)
        hits.sort(
            key=lambda h: (h.confidence, len(h.matched_pattern)),
            reverse=True,
        )
        return hits[:max_results]

    def best(self, text: str) -> TranslatedError | None:
        """Convenience: return the single best translation, or ``None``."""
        results = self.translate(text, max_results=1)
        return results[0] if results else None

    def __len__(self) -> int:  # pragma: no cover — trivial
        return len(self._entries)


__all__ = [
    "VnErrorTranslator",
    "TranslatedError",
    "DEFAULT_DICT_DIR",
]
