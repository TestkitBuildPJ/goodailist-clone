---
name: vck-office-hours
description: YC-style product interrogation — 6 forcing questions (PMF / retention / moat / growth / ask / risk)
argument-hint: "[product_pitch_or_plan]"
allowed-tools: read, grep, tool:thinking
inspired-by: gstack/.claude/commands/office-hours/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-office-hours — YC Office Hours simulator (VN-first)

**Mục tiêu:** ép founder / PM trả lời thẳng 6 câu hỏi khó trước khi cho
đi tiếp.  Áp dụng sau `/vibe-rri` CHALLENGE và trước `/vibe-vision`.

## Khi nào gọi

- Trước khi chốt OKR / spec một feature lớn (> 2 sprint).
- Khi có dấu hiệu scope creep (TIP phình > 1,500 LOC, > 3 persona).
- Khi user kể "chúng ta cần build cái mới" nhưng chưa data retention.

## 6 câu hỏi bắt buộc (ORDER MATTERS)

1. **PMF signal** — "Ai dùng sản phẩm mỗi tuần?  N=?  Retention tuần
   4 = ?  Nếu tôi tắt tính năng hôm nay, ai sẽ email bạn?"
2. **What hurts** — "Đau duy nhất mà sản phẩm này giải quyết là gì?
   Nói 1 câu, tiếng Việt.  Nếu phải xoá 1 feature mà không ai nhận ra
   trong 30 ngày, feature nào?"
3. **Why now** — "Điều gì 2 năm trước chưa đúng mà hôm nay đúng?
   (tech trend / price curve / regulation / behaviour shift)"
4. **Moat** — "Sau 18 tháng, đối thủ lớn nhất (Google / Meta / một YC
   batch) copy được gì và không copy được gì?  Tại sao?"
5. **Distribution** — "Người thứ 1000 biết đến sản phẩm từ đâu?
   CAC trần = ?  LTV sàn = ?  Nếu CAC > LTV / 3, kế hoạch B là gì?"
6. **The ask** — "Hôm nay tôi (partner) có thể giúp gì cụ thể trong
   30 phút?  (intro / hiring / unblock / punt)"

## Output (fail-fast)

```
YAML
verdict: GO | PIVOT | HOLD | KILL
red_flags:
  - <1-line / flag>
strongest_signal: <1-line>
biggest_risk: <1-line>
next_30d: <≤3 bullet, mỗi bullet ≤ 12 từ>
```

## Gate (pass/fail)

- **GO** ⇔ trả lời 6/6 với dữ liệu cụ thể (số, tên user thật, URL).
- **PIVOT** ⇔ 1 câu (thường #1 hoặc #4) không có số → đổi scope.
- **HOLD** ⇔ 2+ câu mơ hồ → ngưng build, quay về `/vibe-scan` + user interview.
- **KILL** ⇔ 3+ câu mơ hồ hoặc #1 trả "chưa ai dùng hết tuần 2" → đóng.

## Integration trong VIBECODE-MASTER

```
/vibe-scan → /vibe-rri CHALLENGE → /vck-office-hours → /vibe-vision
                                         │
                                         └─→ PIVOT / HOLD / KILL blocks progress
```

Thất bại ở đây KHÔNG được phép bypass bằng cách đi thẳng `/vibe-task graph`.

## Attribution

Port từ gstack `office-hours` (© Garry Tan, MIT).  VN-first adaptation,
no upstream code copied.  Xem `LICENSE-third-party.md`.
