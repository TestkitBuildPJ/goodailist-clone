---
name: vck-retro
description: Weekly retro — tổng hợp learnings 7 ngày, phân loại keep/stop/try, sinh 3 commit action
argument-hint: "[--days 7]"
allowed-tools: read, write, tool:thinking
inspired-by: gstack/.claude/commands/retro/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-retro — retro hàng tuần (VN-first)

Đọc `.vibecode/learnings.*.jsonl` + git log 7 ngày → tổng hợp 3 bucket
**Keep / Stop / Try** + đề xuất 3 action commit.

## Pipeline

1. Load learnings (user + team + project) via
   `scripts/vibecodekit/learnings.py`.
2. Lọc theo `--days` (mặc định 7).
3. Classify:
   - **Keep** — pattern đã áp dụng thành công ≥ 2 lần.
   - **Stop** — pattern hoặc tool gây lỗi ≥ 1 P0 hoặc ≥ 3 rework.
   - **Try** — giả thuyết chưa xác nhận, cần 1 sprint thử.
4. Sinh 3 action, mỗi action 1 commit sketch:
   - `docs(retro): <what> @ week <n>` — cập nhật `CHANGELOG.md` /
     `references/`.
   - `chore(retro): <what>` — tự động hoá learning (hook, probe, CI).
   - `refactor(retro): <what>` — nếu keep → codify thành utility.

## Output

```markdown
# Retro tuần <YYYY-W##>

## Keep
- ...

## Stop
- ...

## Try
- ...

## Actions (3 commit)
1. `docs(retro): ...`
2. `chore(retro): ...`
3. `refactor(retro): ...`
```

## Integration

- Chạy cuối sprint / cuối tuần.
- Output commit vào branch `retro/<YYYY-W##>`, PR gửi cho team.

## Attribution

Port từ gstack `retro` (© Garry Tan, MIT).  VN-first.
