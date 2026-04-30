---
name: vck-design-review
description: Audit a shipped UI against design system + atomic fix loop
argument-hint: "[page_or_url_or_screenshot]"
allowed-tools: read, grep, tool:thinking
inspired-by: gstack/.claude/commands/design-review/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-design-review — audit UI + atomic fix loop (VN-first)

Đối chiếu 1 màn hình / URL với design system (`/vck-design-consultation`
output).  Không vote, chỉ list **drift** và đề xuất commit-atomic
từng fix.

## Phạm vi audit (8 checklist)

1. **Token drift** — có màu / font-size / spacing không thuộc token set?
2. **Component drift** — có biến thể Button / Input không phải từ library?
3. **Spacing rhythm** — padding/margin có tuân 4pt scale?
4. **Typography** — hierarchy (H1 > H2 > body > caption) rõ?
5. **A11y** — contrast ≥ 4.5:1 body, 3:1 large; focus ring; alt text;
   keyboard nav đi hết flow.
6. **VN text** — dấu không vỡ; date format DD/MM; số thập phân `,`;
   tiền VND với hậu tố ₫; tên giữ dấu chứ không strip.
7. **Empty / error / loading state** — cả 3 tồn tại và có copy.
8. **Micro-interaction** — hover / active / disabled thấy được; không
   dùng toast để báo lỗi validation inline.

## Atomic fix loop

Mỗi drift → 1 commit riêng:
- Subject: `fix(ui): <short description>`.
- Body: trích checklist item + before/after (≤ 80 cột ASCII).
- Touch ≤ 20 file mỗi commit, không lẫn logic change.

## Output

```yaml
audited: <page_or_url>
drifts:
  - id: D-01
    checklist: 3  # spacing rhythm
    severity: high|med|low
    fix_commit_subject: "fix(ui): align form padding to 4pt scale"
followup_runs:
  - /vibe-rri-ui CRITIQUE
  - /vck-qa-only
```

## Integration

- Gọi sau bất kỳ PR nào động vào UI.
- Blocking: severity=high ≥ 1 → chặn merge (failed `/vck-ship` QA
  gate).

## Attribution

Port từ gstack `design-review` (© Garry Tan, MIT).
Clean-room rewrite.
