"""Token-ranked memory retrieval with Vietnamese diacritic support (Pattern #11).

The retrieval layer splits standard memory files into header-chunks and ranks
them by query-token overlap.  v0.7 normalises *query* and *document* to NFC
and strips diacritics for matching, so Vietnamese tokens are reached even when
the user searches without dấu.
"""

from __future__ import annotations

import math
import os
import re
import unicodedata
from pathlib import Path

MEMORY_FILES = (
    "PROJECT_MEMORY.md",
    "TEAM_MEMORY.md",
    "USER_MEMORY.md",
    "CLAUDE.md",
    ".vibecode/memory/project-memory.md",
    ".vibecode/memory/team-memory.md",
)

_TOKEN_RX = re.compile(r"[\w\u00c0-\u024f]+", re.UNICODE)


def _strip_diacritics(s: str) -> str:
    # Decompose → drop combining marks → recompose.
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def tokenize(text: str) -> set[str]:
    text = unicodedata.normalize("NFC", text).casefold()
    text = _strip_diacritics(text)
    return set(m.group(0) for m in _TOKEN_RX.finditer(text))


def load_memories(root: str | os.PathLike) -> list[dict[str, str]]:
    root = Path(root)
    chunks: list[dict[str, str]] = []
    for rel in MEMORY_FILES:
        p = root / rel
        if not p.exists():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        # Split by markdown headers; keep each header + body as its own chunk.
        current_header = "(top)"
        current_body: list[str] = []

        def flush():
            if current_body:
                chunks.append(
                    {
                        "source": str(rel),
                        "header": current_header,
                        "text": "\n".join(current_body).strip(),
                    }
                )

        for line in text.splitlines():
            if line.startswith("#"):
                flush()
                current_header = line.strip()
                current_body = []
            else:
                current_body.append(line)
        flush()
    return chunks


def retrieve(root: str | os.PathLike, query: str, limit: int = 8) -> list[dict]:
    q = tokenize(query)
    out: list[dict] = []
    for c in load_memories(root):
        toks = tokenize(c["text"] + " " + c["header"])
        if not toks:
            continue
        overlap = len(q & toks)
        if overlap == 0:
            continue
        score = overlap / (1.0 + math.log(1.0 + len(toks)))
        out.append({**c, "score": round(score, 4), "overlap": overlap})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]
