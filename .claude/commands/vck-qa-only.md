---
description: "Real-browser QA — chỉ chạy checklist, không fix loop (CI / pre-merge gate)"
version: 0.12.0
allowed-tools: [Bash, Read]
inspired-by: "gstack/qa/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
deprecated: true
replaced-by: /vck-qa
removal-target: v1.0.0
deprecation-note-vn: "`/vck-qa-only` chỉ là phiên bản no-fix-loop của `/vck-qa`; dùng `/vck-qa` (đã có toggle CI gate qua exit code) thay thế. Giữ đến v1.0.0 cho backward compat."
---

# /vck-qa-only — QA without fix loop

Phiên bản chỉ-đọc của `/vck-qa`. Dùng cho:
- CI step: `python -m vibecodekit.cli qa --only --url $STAGING_URL`
- Pre-merge gate trong `/vck-ship`
- Manual smoke test khi không muốn skill auto-edit code

Không có fix loop, không apply diff. Output cùng format như `/vck-qa` nhưng exit code khác:
- `0` — GREEN (pass 12/12)
- `1` — YELLOW (pass ≥ 9/12)
- `2` — RED (pass < 9/12)

Xem `/vck-qa` cho checklist đầy đủ và mô tả checklist VN-12.

## Hậu xử lý (v0.15+)

Sau khi qa pass GREEN (exit 0), ghi vào session ledger để `/vck-ship`
Bước 0 nhận diện:

```bash
python -m vibecodekit.team_mode record --gate /vck-qa-only
```

Trên repo không có team mode thì câu lệnh vẫn an toàn (no-op semantic).

> Skill này được port + Việt-hoá từ [gstack/qa](https://github.com/garrytan/gstack/tree/main/qa) (© Garry Tan, MIT). Xem `LICENSE-third-party.md`.
