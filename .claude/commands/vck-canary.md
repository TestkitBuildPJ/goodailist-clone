---
description: "Post-deploy canary — quét health, error rate, latency trong 30 phút sau ship"
version: 0.12.0
allowed-tools: [Bash, Read]
inspired-by: "gstack/canary/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
voice-triggers:
  - "canary"
  - "kiểm tra deploy"
  - "post deploy"
---

# /vck-canary — Post-Deploy Monitor (VN)

Sau khi `/vibe-ship` deploy thành công, gọi `/vck-canary` để theo dõi 30 phút **không-rời-mắt**: error rate, latency p95, healthcheck, log anomaly.

> Triết lý: **một deploy chỉ thực sự xong khi canary xanh**. Trước canary xanh, đừng bắt đầu task mới. Đừng đi lunch. Đừng "trust the tests."

## Pipeline 4 phase × 30 phút

### Phase 1 — t0 → t+5 min: Smoke
- Healthcheck `/health` mọi 10s, 30 lần
- 1 request `/api/canary` happy path
- 1 request happy path với auth cao nhất
- Pass-gate: 100% green

### Phase 2 — t+5 → t+15: Error rate baseline
- Lấy error rate từ APM/Sentry/Logs/CloudWatch
- So với baseline 1h trước
- **Pass-gate:** error rate ≤ baseline × 1.2

### Phase 3 — t+15 → t+25: Latency
- p50, p95, p99 từ APM
- **Pass-gate:** p95 ≤ baseline × 1.3 và p99 ≤ baseline × 1.5

### Phase 4 — t+25 → t+30: Log anomaly
- Top 10 error pattern trong 30 phút
- Có pattern mới (chưa thấy trước đây) không?
- **Pass-gate:** 0 pattern mới có severity ≥ ERROR

## Decision matrix

| Pass | Action |
|---|---|
| 4/4 phase | GREEN — đóng canary, mark deploy success, log vào `runtime/deploys/` |
| 3/4 (chỉ Phase 4) | YELLOW — escalate, ghi vào TODOS, không rollback |
| 2/4 hoặc kém hơn | RED — auto-rollback (gọi `/vibe-ship rollback <last>`), gửi alert |

## Lệnh

| Cú pháp | Mô tả |
|---|---|
| `/vck-canary` | Bắt đầu canary 30 phút cho deploy gần nhất |
| `/vck-canary --target prod` | Chỉ định target |
| `/vck-canary --duration 60` | Tăng thời gian (phút) |
| `/vck-canary --auto-rollback no` | Không rollback tự động (chỉ alert) |

## Output

```
# /vck-canary report — deploy abc123 → prod
- t0: 2026-04-28T10:00Z
- Phase 1 smoke: PASS
- Phase 2 error rate: PASS (0.3% vs baseline 0.2%, ratio 1.5x — borderline)
- Phase 3 latency: PASS (p95 240ms vs 200ms = 1.2x)
- Phase 4 anomaly: PASS

Status: GREEN — deploy confirmed
```

## Tích hợp `/vibe-ship`

Tự động chèn `/vck-canary` sau `/vibe-ship` khi:
- Target `prod` (không phải staging)
- Có `feature flag` mới
- Có DB migration trong commit

> Skill này được port + Việt-hoá từ [gstack/canary](https://github.com/garrytan/gstack/tree/main/canary) (© Garry Tan, MIT). Xem `LICENSE-third-party.md`.
