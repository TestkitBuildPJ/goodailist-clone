---
description: "Orchestrator: test → review → commit → push → PR (atomic, gate-driven)"
version: 0.12.0
allowed-tools: [Bash, Read, Write]
inspired-by: "gstack/ship/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
voice-triggers:
  - "ship"
  - "đưa code lên"
  - "tạo PR"
  - "ship code"
---

# /vck-ship — Ship Orchestrator (VN)

Lệnh ship-cuối: chạy tuần tự **test → /vck-review → commit → push → PR**, gate-driven, không bỏ qua bước.

> Khác `/vibe-ship` (deploy 7-target): `/vck-ship` chỉ là **code-ship** (đưa code đi review/PR). Sau khi PR merge, gọi `/vibe-ship` để deploy.

## Pipeline 7 bước

### Bước 0 — Team-mode preflight (v0.15+)
```bash
python -m vibecodekit.team_mode check
```
- No-op nếu repo không có `.vibecode/team.json` (exit 0).
- Nếu có team config: đọc `.vibecode/session_ledger.jsonl` và assert
  rằng tất cả gate trong `required` đã chạy ở session hiện tại.
- **Gate:** exit 0 = pass. Exit 2 = `TeamGateViolation` →
  STOP, in danh sách gate còn thiếu, hướng dẫn user chạy `/vck-review`
  + `/vck-qa-only` rồi rerun `/vck-ship`.

### Bước 1 — Preflight
- `git status` clean (không có untracked không trong .gitignore)
- Branch không phải `main` / `master`
- Có ít nhất 1 commit kể từ base branch
- `python -m vibecodekit.cli doctor` pass

### Bước 2 — Test gate
**v0.15+ — diff-based selective khi có `tests/touchfiles.json`:**

```bash
BASE=${VCK_SHIP_BASE:-origin/main}
if [ -f tests/touchfiles.json ]; then
  python -m vibecodekit.eval_select --base "$BASE" --map tests/touchfiles.json --json > /tmp/vck-selected.json
  SELECTED=$(python -c "import json; d=json.load(open('/tmp/vck-selected.json')); print(' '.join(d.get('selected') or []))")
  if [ -n "$SELECTED" ]; then
    PYTHONPATH=./scripts python3 -m pytest -q $SELECTED
  else
    PYTHONPATH=./scripts python3 -m pytest tests -q   # diff empty → fallback full
  fi
else
  PYTHONPATH=./scripts python3 -m pytest tests -q     # no map → full suite
fi
```

**Gate:** `0 failed, 0 errored`. Nếu fail → STOP, không commit.

### Bước 3 — `/vck-review` gate
- Spawn `/vck-review` trên `git diff <base>`
- **Gate:** recommendation = GREEN. YELLOW → ask user confirm. RED → STOP.
- Sau khi review pass: `python -m vibecodekit.team_mode record --gate /vck-review`

### Bước 4 — `/vck-qa-only` gate (nếu có UI)
- Detect: có file `*.tsx`, `*.jsx`, `*.vue`, `*.svelte` trong diff?
- Nếu có: chạy `/vck-qa-only $STAGING_URL` (yêu cầu env `VCK_STAGING_URL`)
- **Gate:** exit code 0 (GREEN)
- Sau khi qa pass: `python -m vibecodekit.team_mode record --gate /vck-qa-only`

### Bước 5 — Commit + push
- Conventional commit: `feat(<scope>): <subject>`
- Body: liệt kê findings đã fix từ /vck-review
- Footer: `Reviewed-by: /vck-review (7 specialists)`
- `git push -u origin <branch>` (push thường, không force)

### Bước 6 — PR
- Fetch template `git_pr fetch_template` (nếu repo có)
- Body theo template + summary của review findings + test result
- Tạo PR, lấy URL trả về user

### Bước 7 — Clear ledger (v0.15+)
```bash
python -m vibecodekit.team_mode clear
```
- Wipe `.vibecode/session_ledger.jsonl` để cycle ship kế tiếp bắt đầu sạch.

## Lệnh

| Cú pháp | Mô tả |
|---|---|
| `/vck-ship` | Full pipeline 7 bước (Bước 0 → Bước 7) |
| `/vck-ship --skip-qa` | Bỏ bước 4 (cho repo không có UI) |
| `/vck-ship --draft` | Tạo draft PR thay vì ready |
| `/vck-ship --dry-run` | Chạy bước 0-4, không commit/push/PR |
| `/vck-ship --base develop` | Base branch khác `main` |

## Failure modes

| Bước fail | Action |
|---|---|
| 0 (team-mode preflight) | Exit 2 = `TeamGateViolation`. STOP, in danh sách gate còn thiếu (ví dụ `/vck-review` chưa chạy), hướng dẫn user chạy gate đó rồi rerun `/vck-ship`. No-op (exit 0) khi repo không có `.vibecode/team.json`. |
| 1 (preflight) | STOP, hướng dẫn user clean state |
| 2 (test) | STOP, show test output, gợi ý `/vck-investigate` |
| 3 (review) | RED → STOP. YELLOW → ask. |
| 4 (qa) | STOP, show /vck-qa report |
| 5 (push) | Nếu remote rejected (protected branch) → suggest tạo branch mới |
| 6 (PR) | Nếu API fail → save commit local, hướng dẫn user tạo PR thủ công |
| 7 (clear ledger) | Non-blocking: PR đã mở thành công ở Bước 6 nên không cần STOP. Nếu `team_mode clear` báo OSError (permission/disk) → log warning + chạy lại bằng tay `python -m vibecodekit.team_mode clear` trước cycle ship kế tiếp. |

## Output

```
# /vck-ship report
[OK] Preflight
[OK] Tests: 399 passed
[OK] /vck-review: GREEN (3 medium, 0 high, 0 critical)
[OK] /vck-qa-only: 12/12 (GREEN)
[OK] Commit: feat(api): add login endpoint (a1b2c3d)
[OK] Push: origin/feat/login
[OK] PR: https://github.com/.../pull/42
```

## Tích hợp VIBECODE-MASTER

`/vck-ship` thay thế phase **VERIFY** chuẩn của VIBECODE-MASTER khi có UI/critical code. Phase REFINE chạy sau khi PR merged + `/vck-canary` báo healthy.

> Skill này được port + Việt-hoá từ [gstack/ship](https://github.com/garrytan/gstack/tree/main/ship) (© Garry Tan, MIT). Xem `LICENSE-third-party.md`.
