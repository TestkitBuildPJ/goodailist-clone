---
description: "Root-cause debug — NO-FIX-WITHOUT-INVESTIGATION"
version: 0.12.0
allowed-tools: [Bash, Read, Grep, Glob]
inspired-by: "gstack/investigate/SKILL.md.tmpl @ commit 675717e3"
license: "MIT — see LICENSE-third-party.md"
voice-triggers:
  - "debug"
  - "tại sao"
  - "investigate"
  - "vì sao lỗi"
---

# /vck-investigate — Root Cause Investigation (VN)

> **Quy tắc bất di bất dịch:** **NO-FIX-WITHOUT-INVESTIGATION.** Không có fix nào được commit nếu chưa có investigation report tối thiểu 5-Why hoặc fishbone.

## Khi nào dùng

- Test fail + không hiểu lý do
- Production incident (5xx tăng đột biến, latency spike)
- "Why does X happen sometimes?" — flaky test, race condition
- Trước khi gọi `/vck-ship` cho hot-fix

## 4 phase

### Phase 1 — Reproduce (10 phút)
- Reproduce 100% trên local? Hay chỉ flaky?
- Repro với input tối thiểu — strip mọi thứ không liên quan
- Document: input, env, version, expected vs actual

### Phase 2 — Bisect (15 phút)
```bash
git bisect start
git bisect bad HEAD
git bisect good <last-known-good>
# bisect tự run test command bạn cung cấp
```
Hoặc bisect theo log:
- Khi nào lần đầu thấy lỗi trong logs?
- Deploy nào diff với deploy trước đó?

### Phase 3 — 5-Why (15 phút)
```
Q1: Tại sao request này 500?
A1: Vì DB query trả NULL.

Q2: Tại sao DB query trả NULL?
A2: Vì JOIN miss key.

Q3: Tại sao JOIN miss key?
A3: Vì column user_id ở bảng B đổi type sang BIGINT, bảng A vẫn INT.

Q4: Tại sao đổi không sync?
A4: Vì migration M042 chỉ update bảng B, không có bảng A.

Q5: Tại sao migration không catch điều này?
A5: Vì không có CI step verify FK type consistency.
```
→ **Root cause:** thiếu CI step. Fix: thêm step + sửa M042 backfill.

### Phase 4 — Investigation report

```
# Investigation: <title>
- Severity: CRITICAL/HIGH/MED/LOW
- Status: Active/Mitigated/Resolved
- Repro: <steps tối thiểu>
- Expected: …
- Actual: …
- Root cause: <từ 5-why phase 3>
- Fix proposal: <diff or design>
- Prevention: <CI step, test, monitoring>
- Affected commits: <list>
```

## Lệnh

| Cú pháp | Mô tả |
|---|---|
| `/vck-investigate <title>` | Mở investigation mới |
| `/vck-investigate --bisect` | Auto bisect với test command từ stdin |
| `/vck-investigate --5why` | Force 5-why mode |

## Tích hợp /vck-ship

`/vck-ship` block nếu commit hiện tại nói "fix" / "hotfix" mà không có file `runtime/investigations/<id>.md`. Audit probe verify.

## Output: ghi vào `runtime/investigations/`

```
runtime/investigations/2026-04-28-flaky-auth-test.md
```

> Skill này được port + Việt-hoá từ [gstack/investigate](https://github.com/garrytan/gstack/tree/main/investigate) (© Garry Tan, MIT). Xem `LICENSE-third-party.md`.
