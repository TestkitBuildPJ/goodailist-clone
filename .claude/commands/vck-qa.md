---
description: "Real-browser QA — sub-second checklist trên Chromium thật (Phase 1 wires Python daemon)"
version: 0.12.0
allowed-tools: [Bash, Read, Write]
inspired-by: "gstack/qa/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
voice-triggers:
  - "qa"
  - "kiểm tra giao diện"
  - "browser test"
  - "smoke test"
---

# /vck-qa — Real-browser QA (VN)

Quét trang/feature trên **Chromium thật** (qua Python browser daemon — xem `scripts/vibecodekit/browser/`) bằng checklist VN-12 + fix loop tự động.

## Yêu cầu

```bash
pip install "vibecodekit-hybrid-ultra[browser]"
playwright install chromium
```

Sau đó CLI có sẵn:
```bash
python -m vibecodekit.browser.cli_adapter goto https://staging.example.com
python -m vibecodekit.browser.cli_adapter snapshot
```

## Lệnh

| Cú pháp | Mô tả |
|---|---|
| `/vck-qa <url>` | Full checklist VN-12 + fix loop (≤ 5 vòng) |
| `/vck-qa-only <url>` | Chỉ chạy checklist, không fix |
| `/vck-qa <url> --persona elderly` | Chạy persona-bias (RRI-UX 5 personas) |
| `/vck-qa <url> --mobile` | Force viewport 375×812 |

## Checklist VN-12

| # | Hạng mục | Kiểm tra |
|---|---|---|
| 1 | **Load** | First contentful paint ≤ 2s trên 3G slow? |
| 2 | **Console** | Có error JS đỏ không? Có warning hydration không? |
| 3 | **Network** | Có request 4xx/5xx không cần thiết? Có request không có CORS? |
| 4 | **A11y** | Aria-label các button/icon có đủ? Keyboard tab path đúng? |
| 5 | **Empty state** | Khi không có data, có empty state có CTA không? |
| 6 | **Loading state** | Loading có skeleton hoặc spinner? Không nhảy layout? |
| 7 | **Error state** | Khi API fail, error có message tiếng Việt + retry CTA? |
| 8 | **Form validation** | Validation hiện ngay khi blur? Message tiếng Việt? Inline không alert()? |
| 9 | **Mobile** | Tap target ≥ 44×44? Không overflow horizontal? |
| 10 | **Dark mode** | Toggle dark có hoạt động? Contrast trong dark ≥ 4.5:1? |
| 11 | **i18n** | VN-first, có chỗ nào còn hardcoded English? |
| 12 | **VN context** | Có format ngày dd/mm/yyyy? Số có dấu chấm hàng nghìn? Tiền VNĐ có ký hiệu ₫? |

## Fix loop (≤ 5 vòng)

```
Loop:
  1. Snapshot trang (DOM + a11y tree + console + network)
  2. Run 12 check
  3. Nếu pass tất cả → emit report GREEN, exit
  4. Nếu fail:
       a. Show finding cho user
       b. Đề xuất fix (diff)
       c. Apply nếu approve (qua permission_engine)
       d. Reload trang
  5. Vòng > 5 → emit report YELLOW + escalate
```

## Output

```
# /vck-qa report — <url> @ <timestamp>
- Vòng fix: <n>/5
- Status: GREEN / YELLOW / RED
- Pass: <m>/12

## Findings
### V03 [HIGH] Network — /api/users 500 sau 2s
- Repro: Goto <url> → click "Tải"
- Console: …
- Suggested fix: …
```

## Tích hợp /vck-qa-only

Cùng skill backend nhưng KHÔNG có fix loop. Dùng cho CI / pre-merge gate.

## Tích hợp permission_engine

Mọi browser command (`browser:goto`, `browser:click`, `browser:fill`) đi qua `permission_engine.classify_cmd("browser:...")`. Audit probe #58 verify điều này.

> Skill này được port + Việt-hoá từ [gstack/qa](https://github.com/garrytan/gstack/tree/main/qa) (© Garry Tan, MIT). Browser daemon là implementation Python độc lập — xem `BROWSER.md` (Phase 1). Xem `LICENSE-third-party.md`.
