# 36 — Copy patterns (headlines, CTA, social-proof, pricing, empty/error, VN rules)

> Port of **VIBECODE-MASTER-v5.txt** Phụ Lục D (Common Copy Patterns),
> extended in v0.11.2 with pricing copy, empty-state copy, error-state
> copy, and Vietnamese-first copy rules.  Both `/vibe-vision` and
> `/vibe-rri-ui` consult this file when iterating microcopy; the lists
> are stable and machine-readable through `methodology.COPY_PATTERNS`.
>
> Style/typography tokens (font pairings, color psychology, VN typography)
> live in `references/34-style-tokens.md` — keep §3 (this file's scope)
> separate from §B/C (that file's scope).
>
> Do not renumber existing IDs; add new entries with the next free numeric ID.

## 1. Headlines (CF-01..CF-03)

| ID    | Formula                            | VI example                                        | EN example                                |
|-------|------------------------------------|---------------------------------------------------|-------------------------------------------|
| CF-01 | `[Số] + [Timeframe] + [Outcome]`   | "Đẹp 10x trong 5 phút"                            | "Ship 10x faster in 5 minutes"           |
| CF-02 | `[Verb] + [Object] + [Benefit]`    | "Thanh toán hoá đơn không sai số"                 | "Send invoices without spreadsheet pain" |
| CF-03 | `[Question that resonates]`        | "Bạn đã chán việc nhập tay từng ngày?"            | "Tired of copy-pasting orders by hand?"  |

Pick **exactly one** primary headline per page. Do not stack CF-01/02/03
together; the eye reads only the topmost line in 5 seconds.

## 2. Calls-to-action (CF-04)

| ID    | Formula                            | VI example                                        | EN example                                |
|-------|------------------------------------|---------------------------------------------------|-------------------------------------------|
| CF-04 | `[Action verb] + [Value]`          | "Nhận báo giá miễn phí"                           | "Get my free invoice template"           |

- **Length:** ≤ 4 từ tiếng Anh, ≤ 6 từ tiếng Việt.
- **Above-the-fold primary CTA** must be the single most contrasting
  button on the viewport.
- Never start a Vietnamese CTA with the verb `"Nhấn"` / `"Click"` — that
  is meta-copy, not value copy.

## 3. Social proof (CF-05..CF-06)

| ID    | Formula                                                | Notes |
|-------|--------------------------------------------------------|-------|
| CF-05 | **Logo bar 5–7 logos**                                 | Brand-recognition bar — never < 5 (looks lonely) and never > 7 (looks like a stock photo). Logos must be monochrome on neutral background to avoid hue clash. |
| CF-06 | **Testimonial: face + quote ≤ 25 words + role + company** | Quote phải có 1 con số cụ thể (`tăng 32% conversion`), không phải adjective rỗng (`amazing`). Tag the persona that the testimonial validates. |

## 4. Pricing copy (CF-07)

| ID    | Pattern                                                                                              | VI example                                  | EN example                              |
|-------|------------------------------------------------------------------------------------------------------|---------------------------------------------|-----------------------------------------|
| CF-07 | `[Tier name] · [Price] · [Unit] · [Anchor benefit, ≤ 6 words]`                                       | "Starter · 199.000 ₫ · /tháng · 5 dự án"     | "Starter · $9 · /mo · 5 projects"       |

**Vietnamese pricing rules (must apply to any VND figure):**

- Use **dot as thousands separator** and **`₫` (U+20AB) suffix** with
  a non-breaking space: `"199.000\u00A0₫"`.  Never `"199,000 VND"`.
- Show `/tháng` for monthly (not `/th`, not `/m`).
- Anchor benefit must be **concrete**: number of projects, seats, GB,
  or transactions.  Forbidden: `"unlimited"` (phải nói rõ giới hạn fair-use),
  `"all features"` (phải liệt kê 3 tính năng đáng giá nhất).
- Comparison row: **monthly** anchor, **yearly** discount as `–20%` not
  `"save 20%"`.

## 5. Empty-state copy (CF-08)

| ID    | Pattern                                            | VI example                                                                       | EN example                                          |
|-------|----------------------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------|
| CF-08 | `[Verb] + [Outcome]` + primary CTA, no "No data."  | "Bắt đầu tạo dự án đầu tiên — chỉ mất 1 phút."                                   | "Create your first project — takes 1 minute."     |

- Forbidden phrasing: `"Không có dữ liệu"`, `"No data"`, `"Empty"`,
  illustration without a verb, sad-icon-only.
- Always include a CTA that resolves the empty state in **one click**.
- For filtered empty states (search returned 0): tell user *what* they
  searched and offer "Clear filters" + "Try X" link.

## 6. Error-state copy (CF-09)

| ID    | Pattern                                                                                            | VI example                                                                       | EN example                                          |
|-------|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|-----------------------------------------------------|
| CF-09 | `[What happened, ≤ 12 words] + [What to do, ≤ 8 words] + [Optional: trace ID for support]`         | "Không lưu được. Mạng đang chậm — thử lại sau 10s. (#err-32a4)"                  | "Save failed. Network is slow — try again in 10 s. (#err-32a4)" |

- Forbidden phrasing: `"Lỗi xảy ra"`, `"Error occurred"`, `"Something went wrong"`,
  generic 4xx/5xx status as user-facing copy.
- Always answer the user's two questions: **what happened** and **what
  do I do next**.  Include the trace/support ID *only* when there is an
  actual ID to copy — empty trace IDs are noise.
- Tone: blameless. Never `"Bạn đã nhập sai"`; prefer `"Email chưa hợp lệ"`.

## 7. Vietnamese copy rules (CF-VN-01..CF-VN-08)

| ID         | Rule                                                                                                  | Why |
|------------|-------------------------------------------------------------------------------------------------------|-----|
| CF-VN-01   | Không gọi "user" / "system" trong copy người dùng nhìn thấy — gọi "Bạn" / "ứng dụng" / "{tên sản phẩm}". | Translation tells, not localised. |
| CF-VN-02   | Đại từ ngôi thứ hai mặc định là **"Bạn"** (informal-respectful), không phải "Quý khách" trừ B2B/legal.   | "Quý khách" trên consumer SaaS thấy quan cách. |
| CF-VN-03   | Số nhiều: dùng `"các <X>"` thay vì thêm `s` (`các dự án`, không phải `dự áns`).                          | Vietnamese has no plural-s. |
| CF-VN-04   | Định dạng giờ: 24h cho dashboard, 12h+`sáng/chiều/tối` cho consumer.  Định dạng ngày: `dd/MM/yyyy`.    | Consumer expectations differ from UTC dashboards. |
| CF-VN-05   | Định dạng tiền: `199.000 ₫` (xem CF-07). USD: `$9 / tháng` (giữ `$`, đổi `/mo` → `/tháng`).             | Mixed currency on the same screen requires unit harmonisation. |
| CF-VN-06   | Dấu câu: chấm câu bám sát chữ (no thin-space). Dấu hai chấm `:` luôn có khoảng trắng sau, không trước.   | Standard VN typography. |
| CF-VN-07   | Viết hoa: chỉ chữ cái đầu và danh từ riêng — KHÔNG title-case mọi chữ ("Bắt đầu dùng" not "Bắt Đầu Dùng"). | Title-case is an English calque. |
| CF-VN-08   | Tránh borrowed jargon (`onboarding`, `churn`, `retention`) trong copy người dùng — thay bằng từ thuần Việt. | "Hành trình làm quen", "tỉ lệ rời", "tỉ lệ ở lại". |

## 8. Programmatic access

```python
from vibecodekit.methodology import COPY_PATTERNS, lookup_style_token

print(COPY_PATTERNS["CF-01"])  # "[Số] + [Timeframe] + [Outcome]"
print(COPY_PATTERNS["CF-07"])  # "[Tier] · [Price] · [Unit] · [Anchor benefit]"
print(COPY_PATTERNS["CF-08"])  # "[Verb] + [Outcome] + CTA; never 'No data'"
print(COPY_PATTERNS["CF-09"])  # "[What happened] + [What to do] + [Optional trace ID]"

lookup_style_token("CF-04")  # → copy-pattern dict
```

## 9. Cross-reference with Vision template

When `/vibe-vision` proposes a stack the contractor **must** also pick:

- one `CF-01..CF-03` headline pattern for the hero block
- exactly one `CF-04` CTA pattern per page
- a `CF-05` or `CF-06` social-proof pattern when the page targets
  consideration-stage traffic
- `CF-07` for any pricing surface (apply CF-VN-04..05 if VI)
- `CF-08`/`CF-09` for every list/table/form surface (mandatory — no
  raw `"No data"` / `"Error"` permitted in production)
- if shipping in Vietnamese: enforce CF-VN-01..08 in the copy review

Conformance probe `48_copy_patterns_canonical` (added in v0.11.2) verifies
both the markdown list and the methodology constants stay in sync — drift
between this file and `methodology.py` blocks the release gate.
