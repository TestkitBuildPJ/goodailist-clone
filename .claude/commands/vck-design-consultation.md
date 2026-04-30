---
name: vck-design-consultation
description: Build a design system from scratch — tokens → components → patterns → flows
argument-hint: "[product_name_or_persona]"
allowed-tools: read, grep, tool:thinking
inspired-by: gstack/.claude/commands/design-consultation/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-design-consultation — thiết kế design system from zero (VN-first)

Dùng khi sản phẩm chưa có design system.  Output là 1 bundle 4 lớp:

## 4 lớp (order matters)

1. **Tokens**
   - Color: 5 semantic (primary / surface / on-primary / on-surface / muted),
     mỗi cái 9 shade.  VN-friendly: tương phản tối thiểu WCAG AA.
   - Spacing: 4-point scale (4, 8, 12, 16, 24, 32, 48, 64).
   - Typography: 1 serif + 1 sans + 1 mono.  Hỗ trợ dấu tiếng Việt.
   - Radius / elevation: 3 nấc.
2. **Components**
   - Button (primary / secondary / ghost / destructive; size S/M/L).
   - Input (text, textarea, select, checkbox, radio, toggle).
   - Navigation (top nav, side nav, tab, breadcrumb).
   - Feedback (toast, banner, modal, empty state, skeleton).
   - Data (table, list, card, avatar).
3. **Patterns**
   - Login / signup / OTP / reset password.
   - Empty state + first-run onboarding.
   - Error recovery (4xx / 5xx / offline).
   - VN form: tên không dấu fallback, số CMT/CCCD mask, định dạng
     ngày DD/MM/YYYY.
4. **Flows**
   - ≤ 5 happy-path end-to-end flow được vẽ bằng ASCII hoặc Mermaid.

## Gate

- Mọi token có dark-mode twin.
- Tất cả component có focus ring visible (a11y).
- Tất cả pattern có micro-copy tiếng Việt + English.

## Output

```yaml
tokens_path: design/tokens.json
components:
  - name: Button
    file: design/components/button.md
patterns: [...]
flows: [...]
a11y_audit: PASS | FAIL
vn_audit: PASS | FAIL
```

## Integration

Chạy sau `/vibe-rri-ux` và trước `/vibe-rri-ui`.  Output thành input
cho `/vibe-rri-ui DISCOVER`.

## Attribution

Port từ gstack `design-consultation` (© Garry Tan, MIT).
Clean-room rewrite, VN-first additions.
