# 40 — ETHOS-VCK: Triết lý builder của VibecodeKit Hybrid Ultra

> Adapted (with attribution + Vietnamise) từ [gstack/ETHOS.md](https://github.com/garrytan/gstack/blob/main/ETHOS.md) © 2026 Garry Tan, MIT — kết hợp với 3-vai / 8-step VIBECODE-MASTER của VCK-HU. Xem `LICENSE-third-party.md`.

---

## Phần I — Bối cảnh: The Golden Age (Thời kỳ vàng)

Một người + AI giờ build được sản phẩm mà trước đây cần đội 20 kỹ sư. Rào cản kỹ thuật biến mất. Cái còn lại là **gu, sự phán đoán, và sự sẵn sàng làm full**.

| Tác vụ | Đội người | AI-assisted | Hệ số nén |
|---|---|---|---|
| Boilerplate / scaffold | 2 ngày | 15 phút | ~100x |
| Viết test | 1 ngày | 15 phút | ~50x |
| Implement feature | 1 tuần | 30 phút | ~30x |
| Bug fix + regression test | 4 giờ | 15 phút | ~20x |
| Architecture / design | 2 ngày | 4 giờ | ~5x |
| Research / khám phá | 1 ngày | 3 giờ | ~3x |

→ **10% cuối** mà các đội cũ hay bỏ qua (vì hết time/budget)? Giờ chỉ tốn **giây**. Triết lý "đủ là được" của thập kỷ 2010 đã chết.

---

## Phần II — 4 nguyên tắc nền tảng

### 1. Boil the Lake — "Vét cạn cái hồ"

AI làm cho **chi phí biên của hoàn thiện gần bằng 0**. Khi cái version-đầy-đủ chỉ tốn vài phút hơn cái shortcut — **làm cái đầy đủ**. Mọi lần.

- **Lake (hồ)** = boilable. Ví dụ: "100% test coverage cho 1 module", "tất cả error path có message tiếng Việt", "tất cả endpoint có rate limit".
- **Ocean (đại dương)** = không boil được. Ví dụ: "viết AGI từ đầu", "thay thế React".

→ **Quy tắc:** trước mỗi feature, tự hỏi "đây là lake hay ocean?" Nếu là lake — boil 100%. Đừng để 90% rồi bỏ. Đừng để TODO sót lại.

### 2. Search Before Building — "Tìm trước khi build"

Trước khi viết function mới — **search**. Có thể nó đã tồn tại trong:
- Codebase hiện tại (vibe-search, grep, semantic search)
- Standard library (Python stdlib có nhiều thứ bạn không biết)
- Battle-tested package nổi tiếng (requests, pydantic, sqlalchemy)
- Skill `/vck-*` hoặc `/vibe-*` đã có sẵn

Outcome xấu nhất: build version-đầy-đủ của thứ đã tồn tại như 1 dòng code.
Outcome tốt nhất: build version-đầy-đủ của thứ **chưa ai nghĩ ra** — vì bạn đã search và thấy lỗ hổng landscape.

### 3. User Sovereignty — "Chủ quyền người dùng"

Người dùng sở hữu data, sở hữu config, sở hữu workflow. Tool **phục vụ** họ — không khoá họ.

- **Export** mọi thứ. JSON, CSV, sqlite — đừng giam dữ liệu trong proprietary format.
- **Local-first**: Tất cả hoạt động offline trừ khi explicit cần online.
- **Reversible**: Mọi action có undo, rollback, hoặc dry-run.
- **No dark pattern**: Không "are you sure?" 3 lần, không upsell trong critical path.

VCK-HU đã làm điều này: stdlib-only core, runtime data ở `~/.vibecode/`, denial store fcntl-locked, approval JSON contract.

### 4. Build for Yourself — "Build cho chính mình"

Tool tốt nhất giải quyết vấn đề của chính người tạo ra. Mỗi feature build vì **needed**, không vì **requested**. Đặc thù của 1 vấn đề thật **luôn thắng** sự tổng quát của 1 vấn đề giả định.

VCK-HU sinh ra vì author cần methodology rigid + VN-first cho thị trường Việt. Đó là vì sao 87-probe audit (at v0.15.4; was 53 in v0.11.x) + RRI 5×3 + VN-first không thể compromise.

---

## Phần III — Cách 4 nguyên tắc làm việc cùng nhau

```
       Search Before Building
                │
                ▼
       (biết cái gì đã tồn tại)
                │
                ▼
        Build for Yourself ──▶  Boil the Lake
                │                    │
                └──────┬─────────────┘
                       ▼
                User Sovereignty
            (cái bạn build, user kiểm soát)
```

- **Search → Build:** biết landscape trước khi quyết định.
- **Build for Yourself + Boil the Lake:** giải quyết vấn đề thật, full không nửa vời.
- **User Sovereignty:** chuyển quyền cho user, không khoá họ.

---

## Phần IV — Liên kết với VIBECODE-MASTER 8-step

| Step | Nguyên tắc primary |
|---|---|
| 1. SCAN | Search Before Building |
| 2. RRI | Build for Yourself (hỏi rõ user thật cần gì) |
| 3. VISION | Build for Yourself + Boil the Lake (vision phải full) |
| 4. BLUEPRINT | Search Before Building (đừng tái phát minh kiến trúc) |
| 5. TASK GRAPH | Boil the Lake (mọi edge case là 1 task) |
| 6. BUILD | Boil the Lake (không TODO sót) |
| 7. VERIFY | User Sovereignty (test từ góc nhìn user, không developer) |
| 8. REFINE | Tất cả 4 — đặc biệt User Sovereignty (export, rollback) |

---

## Phần V — Anti-pattern phải tránh

| Anti-pattern | Triệu chứng | Ngăn chặn bằng |
|---|---|---|
| "Đủ rồi, fix sau" | TODO sau release, hot-fix tuần sau | Boil the Lake |
| "Tôi tự build cho nhanh" | Recreate `requests` library | Search Before Building |
| "User không cần biết" | Hidden state, no export | User Sovereignty |
| "Sếp bảo build" | Feature không ai dùng | Build for Yourself (or kill it) |
| "Fix without investigation" | Symptom-fix, regression sau | NO-FIX-WITHOUT-INVESTIGATION (xem `/vck-investigate`) |
| "Trust the tests" | Deploy không monitor | Canary mandatory (xem `/vck-canary`) |

---

## Phần VI — Vận dụng trong VCK-HU hằng ngày

- Trước feature: tự hỏi *"Lake hay ocean?"* + *"Có ai làm rồi chưa?"*
- Trước commit: chạy `/vck-review` (7 specialist) — boil cái lake review.
- Trước PR: `/vck-ship` — gate test + review + qa.
- Trước deploy: ETHOS check — user sovereignty còn đảm bảo?
- Sau deploy: `/vck-canary` 30 phút — không-rời-mắt.
- Hàng tuần: `/vck-retro` (P2) — review mọi nguyên tắc bị compromise tuần qua.

---

## Attribution

Bốn nguyên tắc nền tảng (Boil the Lake / Search Before Building / Build for Yourself / User Sovereignty) được adapt từ gstack ETHOS © Garry Tan, MIT. Phần liên kết VIBECODE-MASTER + anti-pattern + ngôn ngữ tiếng Việt là đóng góp của VCK-HU.

> "Trust the search. Boil the lake. Build for yourself. Hand the keys to the user." — gstack ETHOS, adapted.
