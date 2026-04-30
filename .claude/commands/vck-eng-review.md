---
name: vck-eng-review
description: Engineering-mode review — lock architecture, enforce ASCII diagram + state machine + invariants
argument-hint: "[blueprint_or_design_doc]"
allowed-tools: read, grep, glob, tool:thinking
inspired-by: gstack/.claude/commands/eng-review/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-eng-review — Engineering-lens review (VN-first)

Khoá kiến trúc trước khi builder code.  Đầu ra của skill là 1
blueprint **immutable** trong sprint hiện tại — thay đổi chỉ được qua
`/vibe-refine`.

## Gate checklist (7 mục)

1. **ASCII diagram (≤ 80 cột)** — mọi component + data flow.
   Không có diagram = FAIL.
2. **State machine (nếu có trạng thái)** — liệt kê states + transition
   trigger.  Nếu > 8 states → yêu cầu break-out.
3. **Invariants** — liệt kê 3–7 invariants hệ thống phải giữ
   (permission engine là 6 layer, browser state 0o600, hook không được
   block > 200 ms, …).
4. **Data contract** — schema input / output cho mỗi public interface.
5. **Error taxonomy** — 3–5 nhóm lỗi + strategy (retry / escalate /
   drop).
6. **Observability** — log keys, metrics names, trace spans.
7. **Backwards-compat** — ảnh hưởng với 26 `/vibe-*` và 6 `/vck-*`
   command có sẵn.

## Red flags → auto-FAIL

- Không có invariants.
- Dùng "TBD" / "sẽ cập nhật" trong state machine hay data contract.
- Thêm dependency mới không đi kèm kế hoạch fallback stdlib-only.
- Thiết kế có mutable global state ngoài `~/.vibecode/` và `.vibecode/`.

## Output

```yaml
verdict: LOCK | REWORK | BLOCK
diagram_present: true/false
state_machine_present: true/false
invariants: [...]
violations:
  - <checklist_item>: <1-line>
followups_before_build:
  - "<owner>: <what, ≤ 12 từ>"
```

## Integration

Chạy trước `/vibe-task graph`.  Output LOCK → blueprint frozen cho
sprint.  Output REWORK / BLOCK → quay về `/vibe-blueprint`.

## Attribution

Port từ gstack `eng-review` (© Garry Tan, MIT).  Clean-room rewrite.
