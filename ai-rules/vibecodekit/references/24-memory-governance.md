# Memory governance

Vibecode separates **three memory scopes**:

| Scope      | File                           | Owner           | Lifetime           |
|------------|--------------------------------|-----------------|--------------------|
| User       | `USER_MEMORY.md`               | operator        | persists across projects |
| Project    | `PROJECT_MEMORY.md` / `CLAUDE.md` | project arch | project lifetime         |
| Team       | `TEAM_MEMORY.md`               | team lead       | while team exists  |

Plus session-level ephemeral memory:
- `.vibecode/runtime/context.json` (turn-by-turn context snapshot)
- `.vibecode/runtime/*.events.jsonl` (event log)

## Memory extraction
After each auto-compact (Layer 3), the extractor scans the compacted
conversation for:
- decisions ("we decided X because Y")
- invariants ("from now on, X must hold")
- open questions ("TODO: verify X")

and appends them to the relevant scope's memory file.  Duplicates are
skipped via fuzzy match.

## Vietnamese support (v0.7)
`memory_retriever.tokenize()` normalises to NFC, strips diacritics for
matching, and treats Latin-Extended A/B (U+00C0–U+024F) as word
characters.  Queries like `"phan tich"` retrieve chunks written with
`"phân tích"` and vice-versa.

## Retrieval API
```python
from vibecodekit import memory_retriever as mr
hits = mr.retrieve(".", "phan tich rui ro", limit=8)
# -> list of {"source": "PROJECT_MEMORY.md", "header": "...", "text": "...", "score": 0.87, "overlap": 4}
```
