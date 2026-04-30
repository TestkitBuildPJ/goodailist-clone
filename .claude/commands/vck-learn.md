---
name: vck-learn
description: Capture one learning into .vibecode/learnings.jsonl (scope=user|project|team)
argument-hint: "[--scope project|user|team] <text>"
allowed-tools: read, write, tool:thinking
inspired-by: gstack/.claude/commands/learn/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-learn — lưu 1 learning (VN-first)

Ghi 1 bài học vào JSONL store.  Tự replay vào system prompt ở session
sau (xem `scripts/vibecodekit/learnings.py`).

## Syntax

```
/vck-learn "<text>"
/vck-learn --scope project "<text>"
/vck-learn --scope user --tag cache "<text>"
```

## Scope

- `project` (default) — `.vibecode/learnings.jsonl`, không commit.
- `team` — `.vibecode/learnings.team.jsonl`, **commit** vào repo.
- `user` — `~/.vibecode/learnings.jsonl`, cross-project.

## Good learning — bad learning

| Good | Bad |
|---|---|
| "Cache key phải bao gồm tenant id; bugs 2025-10-12" | "fix bug cache" |
| "Permission engine layer 4 chặn ranh giới `/etc/*`; không bypass bằng `env -i`" | "permission engine tốt" |
| "VN input: strip dấu chỉ khi so sánh, không lưu không dấu" | "vn text tricky" |

Ngắn, cụ thể, kèm ngày / tác giả / 1 link (commit SHA / issue).

## Integration (v0.15+)

- `/vck-retro` đọc store để tổng hợp tuần.
- `session_start` hook **mặc định ON** auto-inject 10 learning mới nhất
  (scope project ∪ user) vào system prompt addendum.  Tắt bằng
  `VIBECODE_LEARNINGS_INJECT=0` (xem `update-package/.claw/hooks/session_start.py`).
- Sau khi capture, ghi vào ledger để team-mode (nếu bật) thấy gate đã chạy:
  `python -m vibecodekit.team_mode record --gate /vck-learn`

## Attribution

Port từ gstack `learn` (© Garry Tan, MIT).  Clean-room Python store.
