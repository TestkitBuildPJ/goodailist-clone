---
name: vck-second-opinion
description: Second-opinion review — gọi CLI khác (Codex / Gemini / Ollama) để phản biện plan hoặc code
argument-hint: "[--tool codex|gemini|ollama] [path]"
allowed-tools: read, grep, run_command, tool:thinking
inspired-by: gstack/.claude/commands/codex/SKILL.md.tmpl @ commit 675717e3
license: MIT (adapted)
---

# /vck-second-opinion — gọi brain số 2 (VN-first)

Escape hatch khi nghi ngờ kết luận của agent chính.  Gọi 1 CLI khác
để phản biện.

## Tools

| Tool | Env flag | Lệnh ví dụ |
|---|---|---|
| Codex CLI | `CODEX_CLI` | `codex review --file <path>` |
| Gemini CLI | `GEMINI_CLI` | `gemini review --file <path>` |
| Ollama (local) | `OLLAMA_MODEL` | `ollama run <model> < prompt` |

Permission class: **verify** (read-only external call; đi qua
permission engine layer 6).

## Workflow

1. Đọc file / plan đang nghi ngờ.
2. Build prompt `"Phản biện kết luận sau: <...>.  Trả lời JSON
   {disagree:bool, why:str, risk:[...], alt_plan:[...]}"`.
3. Chạy tool qua `run_command` (được permission engine classify).
4. Parse JSON, in diff và nếu `disagree=true` → escalate qua
   `/vibe-approval`.

## Output

```yaml
tool_used: codex|gemini|ollama
disagree: true|false
why: "…"
risk: ["…"]
alt_plan: ["…"]
approval_ticket: appr-<16hex>   # only when disagree=true
```

## Safety

- Không truyền secrets hay `.env` vào prompt.
- Mọi input đi qua `security_classifier` regex layer trước khi
  gọi tool (để chặn prompt-injection từ file đích).
- Output KHÔNG được auto-apply; phải qua `/vibe-approval`.

## Attribution

Port từ gstack `codex` (© Garry Tan, MIT).  Clean-room rewrite,
multi-tool support.
