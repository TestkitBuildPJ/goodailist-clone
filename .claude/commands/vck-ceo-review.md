---
name: vck-ceo-review
description: CEO-mode review — 4 mode (SCOPE EXPANSION / SELECTIVE / HOLD / REDUCTION)
argument-hint: "[plan_or_spec_path]"
allowed-tools: read, grep, tool:thinking
inspired-by: gstack/.claude/commands/ceo-review/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-ceo-review — CEO-lens review (VN-first)

Đọc plan / spec với 4 ống kính CEO.  Output ở 1 trong 4 mode.  Không
vote tiếp features, chỉ **cut / expand / hold / selective**.

## 4 mode

### 1. SCOPE EXPANSION
Plan quá nhỏ so với ngân sách / window.  Thiếu option value.
→ đề xuất thêm 1–2 bets có upside 10×.

### 2. SELECTIVE
Plan đúng hướng nhưng có 2–4 mục không critical path.
→ đánh dấu "stop-start" cho từng mục: (stop = cắt, start = thêm).

### 3. HOLD
Plan có rủi ro lớn về PMF / regulation / team bandwidth.
→ block tiến độ 1 tuần, yêu cầu thêm data (user interview, spike,
legal memo).

### 4. REDUCTION
Plan quá lớn vs. runway / team.  → cắt ≥ 40 % scope.

## Input format

Chấp nhận markdown hoặc JSON:

```json
{
  "horizon_weeks": 6,
  "team_size": 3,
  "runway_weeks": 20,
  "goals": ["G1", "G2", "G3"],
  "bets": [
    {"name": "B1", "size": "S/M/L", "upside": "…", "risk": "…"}
  ]
}
```

## Output

```yaml
mode: SCOPE_EXPANSION | SELECTIVE | HOLD | REDUCTION
rationale: 3–5 câu, tiếng Việt
cuts: [bet_name, …]           # only when SELECTIVE/REDUCTION
adds: [new_bet, …]            # only when SCOPE_EXPANSION
holds: [bet_name, …]          # only when HOLD
actions_next_7d:
  - "<owner>: <what, ≤ 12 từ>"
metrics_to_watch:
  - "<metric> ≥/≤ <threshold>"
```

## Permission class

Read-only.  Chạy được bởi agent `coordinator` hoặc `reviewer`.

## Integration

Chạy sau `/vibe-vision` và trước `/vibe-blueprint`.  Nếu mode =
HOLD/REDUCTION → block `/vibe-task graph` cho đến khi user apply cuts.

## Attribution

Port từ gstack `ceo-review` (© Garry Tan, MIT).  Clean-room rewrite.
