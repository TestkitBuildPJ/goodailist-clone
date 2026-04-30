---
description: "Adversarial multi-specialist code review (7 perspective: architect/security/perf/a11y/ux/dx/risk)"
version: 0.12.0
allowed-tools: [Bash, Read, Grep, Glob, Agent]
inspired-by: "gstack/review/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
voice-triggers:
  - "review"
  - "review code"
  - "code review"
  - "kiểm tra code"
  - "review army"
---

# /vck-review — Adversarial Pre-PR Review (VN, multi-specialist)

Bạn điều phối **một đội review-army** gồm 7 specialist. Mỗi specialist là 1 vai khác nhau, mỗi người có 1 perspective bias. Đầu ra là tổng hợp **diff-level findings** ưu tiên theo severity, đính kèm fix gợi ý.

> Triết lý: **đừng tin một reviewer**. Nhiều perspective phát hiện vấn đề mà 1 reviewer bỏ qua. Đây là kiểm tra **trước khi gọi /vck-ship hoặc trước PR**.

## Lệnh

| Cú pháp | Mô tả |
|---|---|
| `/vck-review` | Review uncommitted diff hiện tại |
| `/vck-review HEAD~3..HEAD` | Review 3 commit gần nhất |
| `/vck-review main..feature/x` | Review feature branch trước khi PR |
| `/vck-review --fast` | Chỉ chạy 3 specialist top (architect, security, risk) |
| `/vck-review --include security` | Chỉ chạy specialist nhất định |

## 7 Specialist

| # | Tên | Bias / câu hỏi cốt lõi |
|---|---|---|
| 1 | **Architect** | "Layering có đúng không? Có ai đó vi phạm dependency direction không? Có function quá 50 dòng cần tách?" |
| 2 | **Security** | "Có path nào nhận user input mà chưa sanitize? Secret nào lộ? Auth boundary nào yếu?" — link sang `/vck-cso` nếu critical |
| 3 | **Performance** | "N+1 query? Loop trong loop? Tải lazy không cần? Cache miss?" |
| 4 | **Accessibility (a11y)** | "Aria label thiếu? Keyboard nav broken? Contrast ratio dưới 4.5:1? Form không có label?" |
| 5 | **UX** | "Error message có hành động? Loading state có? Empty state có? Dark mode có?" |
| 6 | **DX (Developer Experience)** | "Test có cover happy + edge + error path? README có chỉ rõ cách run? Naming nhất quán?" |
| 7 | **Risk** | "Migration có rollback? Feature flag có? Có logic hard-coded trong env? Có TODO chưa giải quyết?" |

## Pipeline review

### Bước 1 — Diff slice
```bash
git diff <range> --unified=8 > /tmp/vck-review-diff.patch
```

### Bước 2 — Spawn 7 sub-agents song song
Mỗi sub-agent chỉ thấy diff + reference hạn chế. Wire qua `subagent_runtime.spawn_for_command("vck-review", role=<specialist>)`.

### Bước 2.5 — Security perspective: classifier scan-diff (v0.15.2 / Bug #2)

Sub-agent **Security** ngoài việc phỏng vấn diff bằng prompt, còn chạy
`security_classifier --scan-diff <range>` để bổ sung verdict cơ học.
Output JSON merge vào bảng tổng kết Bước 3 — mỗi entry `decision="deny"`
sẽ cộng dồn 1 finding `CRITICAL/security` (regex layer) hoặc `HIGH` nếu
chỉ ML layer (haiku/onnx) vote deny.

```bash
python -m vibecodekit.security_classifier --scan-diff "$BASE" \
  > /tmp/vck-review-classifier.json

# Đọc + parse trong sub-agent Security:
python -c "
import json, sys
out = json.load(open('/tmp/vck-review-classifier.json'))
for v in out['verdicts']:
    if v['decision'] == 'deny':
        print(f\"  classifier:deny  {v['path']}  {v['reason']}\")
"
```

Skill này KHÔNG block khi classifier abstain trên mọi layer — đó là
trạng thái mặc định khi ONNX/Haiku layer chưa cấu hình. Chỉ verdict
`deny` mới đẩy review state sang RED.

### Bước 3 — Synthesize
Tổng hợp findings vào bảng:
```
| # | Severity | Specialist | File:Line | Finding | Suggested fix |
|---|---|---|---|---|---|
| 1 | CRITICAL | security | api/auth.py:42 | Token không verify expiry | Thêm `if exp < now: raise` |
| 2 | HIGH | architect | … | … | … |
```

### Bước 4 — Recommendation
- **GREEN** (≤ 2 medium findings, 0 critical) → ready for PR
- **YELLOW** (≥ 1 high) → fix high trước
- **RED** (≥ 1 critical) → STOP, fix critical, re-run /vck-review

## Tích hợp với /vibe-blueprint + /vck-ship

Pipeline đề xuất:
```
/vibe-blueprint → /vck-eng-review → code → /vck-review → /vck-ship
```

## Output template

```
# /vck-review report — <range>
- Specialists: <list>
- Findings: <n critical / n high / n medium / n low>
- Recommendation: GREEN / YELLOW / RED

## Critical
…

## High
…

## Medium / Low (collapsed unless --verbose)
```

## Hậu xử lý (v0.15+)

Sau khi review hoàn tất với recommendation GREEN/YELLOW (RED → STOP),
ghi vào session ledger để `/vck-ship` Bước 0 nhận diện gate đã chạy:

```bash
python -m vibecodekit.team_mode record --gate /vck-review
```

Trên repo không có `.vibecode/team.json` thì câu lệnh này vẫn an toàn
(chỉ append 1 dòng vào `.vibecode/session_ledger.jsonl`, không gây side effect).

> Skill này được port + Việt-hoá từ [gstack/review](https://github.com/garrytan/gstack/tree/main/review) (© Garry Tan, MIT). Xem `LICENSE-third-party.md`.
