"""3-tier memory hierarchy — Giải phẫu Chương 11.

The book describes an Agentic OS's long-term memory as **three scoped
stores** whose entries are merged by a precedence rule:

    user    — cross-project preferences, private notes, skill bookmarks.
    project — repo-local facts, architectural decisions, ADRs.
    team    — org-wide conventions, release governance, shared playbooks.

Precedence (higher wins at the same key): ``project > team > user`` —
a team convention can be overridden per-project but never by a user's
private preferences.

Each tier maps to a well-known location:

    user     → ~/.vibecode/memory/*.md (+ JSONL)
    project  → <root>/.vibecode/memory/*.md (+ JSONL)
    team     → <root>/.vibecode/memory/team/*.md (or $VIBECODE_TEAM_DIR)

Retrieval is split into two layers:

1. **Lexical layer**: Vietnamese NFKD tokeniser (reused from v0.7
   :mod:`memory_retriever`) — zero dependency, always available.
2. **Embedding layer**: pluggable backend.  Default backend is
   :class:`HashEmbeddingBackend`, a deterministic 256-dim hashing
   embedder (no model download required).  Users who install
   ``sentence-transformers`` can register
   :class:`SentenceTransformerBackend`; users who install
   ``openai`` can register :class:`OpenAIEmbeddingBackend`.

Both layers produce scored chunks.  The final result is the **union**,
sorted by the combined score (normalised to [0, 1]).  A ``top_k`` cap
keeps the payload small; precedence tie-breaks duplicates across tiers.

References:
- ``references/24-memory-governance.md``
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory_retriever import tokenize

# Tier ordering — project wins, then team, then user.
TIER_PRECEDENCE = ("project", "team", "user")


def _user_root() -> Path:
    return Path(os.environ.get("VIBECODE_USER_MEMORY") or Path.home() / ".vibecode" / "memory")


def _team_root(project_root: Path) -> Path:
    env = os.environ.get("VIBECODE_TEAM_DIR")
    if env:
        return Path(env)
    return project_root / ".vibecode" / "memory" / "team"


def _project_root(project_root: Path) -> Path:
    return project_root / ".vibecode" / "memory"


# ---------------------------------------------------------------------------
# Chunk + backend contract
# ---------------------------------------------------------------------------
@dataclass
class Chunk:
    tier: str
    source: str
    header: str
    text: str
    score: float = 0.0
    overlap: int = 0
    embedding_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "source": self.source,
            "header": self.header,
            "text": self.text,
            "score": round(self.score, 4),
            "overlap": self.overlap,
            "embedding_score": round(self.embedding_score, 4),
        }


class EmbeddingBackend:
    """Contract for pluggable embedding providers."""

    name: str = "base"

    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (na * nb)


class HashEmbeddingBackend(EmbeddingBackend):
    """Deterministic 256-dim hashing embedder — no external dependency.

    For each token, hash(token) mod 256 determines the bucket, and the
    embedding is the L2-normalised bucket histogram.  This gives a
    coarse lexical signature that still captures some topical overlap
    without needing a model.
    """

    name = "hash-256"
    DIM = 256

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for tok in tokenize(text):
            # Deterministic hash; Python's hash() is salted per-process so
            # we use a stable 64-bit FNV-1a.
            h = 1469598103934665603
            for b in tok.encode("utf-8"):
                h ^= b
                h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
            vec[h % self.DIM] += 1.0
        # L2 normalise
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class SentenceTransformerBackend(EmbeddingBackend):  # pragma: no cover
    """Wraps ``sentence-transformers`` if installed."""

    name = "sbert"

    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed; run `pip install sentence-transformers`."
            ) from e
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str) -> list[float]:
        return list(self._model.encode(text, normalize_embeddings=True).tolist())


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_BACKENDS: dict[str, EmbeddingBackend] = {"hash-256": HashEmbeddingBackend()}
_DEFAULT_BACKEND = "hash-256"

# Aliases — user-friendly names that resolve to canonical backend names.
# v0.10.3: accept the ``pip install`` package name ``sentence-transformers``
# in addition to the short backend name ``sbert``.
_ALIASES: dict[str, str] = {
    "sentence-transformers": "sbert",
    "st": "sbert",
}


def register_backend(backend: EmbeddingBackend) -> None:
    _BACKENDS[backend.name] = backend


def set_default_backend(name: str) -> None:
    name = _ALIASES.get(name, name)
    if name not in _BACKENDS:
        raise ValueError(f"unknown embedding backend: {name}; known: {list(_BACKENDS)}")
    global _DEFAULT_BACKEND
    _DEFAULT_BACKEND = name


def _try_auto_register_sbert() -> bool:
    """Lazy-register ``SentenceTransformerBackend`` if the library is
    installed.  Returns True on success, False if the optional dependency
    is missing (caller must decide whether to raise or fall back)."""
    if "sbert" in _BACKENDS:
        return True
    try:
        register_backend(SentenceTransformerBackend())
        return True
    except ImportError:
        return False


def get_backend(name: str | None = None) -> EmbeddingBackend:
    """Resolve a backend by name (or None for default).

    v0.10.3.1: when the caller passes a **non-empty** name that fails to
    resolve — either because the optional dependency is missing (sbert
    without ``sentence-transformers`` installed) or the name is unknown —
    raise ``ValueError`` instead of silently downgrading to hash-256.
    Silent fallback is reserved for the ``name is None`` path (resolving
    persisted config), where downgrade is the explicit contract.
    """
    if name:
        resolved = _ALIASES.get(name, name)
        if resolved == "sbert":
            _try_auto_register_sbert()
        if resolved in _BACKENDS:
            return _BACKENDS[resolved]
        # Explicit request that failed to resolve — surface it loudly so
        # users don't get a silent semantic downgrade.
        if resolved == "sbert":
            raise ValueError(
                "embedding backend 'sbert' (sentence-transformers) is not "
                "installed; run `pip install sentence-transformers` or pick "
                "another backend"
            )
        raise ValueError(f"unknown embedding backend: {name!r}; " f"known: {sorted(_BACKENDS)}")
    # name is None — resolve from persisted config, tolerating missing deps.
    try:
        from . import methodology as _meth

        cfg_backend = _meth.get_embedding_backend(default="")
    except Exception:
        cfg_backend = ""
    cfg_backend = _ALIASES.get(cfg_backend, cfg_backend)
    if cfg_backend == "sbert":
        _try_auto_register_sbert()
    if cfg_backend and cfg_backend in _BACKENDS:
        return _BACKENDS[cfg_backend]
    return _BACKENDS[_DEFAULT_BACKEND]


def list_backends() -> list[str]:
    """List registered backend names (excluding aliases).  Attempts to
    auto-register optional backends so the caller can see what is actually
    available in this process."""
    _try_auto_register_sbert()
    return sorted(_BACKENDS.keys())


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _load_tier(tier_dir: Path, tier_name: str) -> list[Chunk]:
    out: list[Chunk] = []
    if not tier_dir.exists():
        return out
    # Markdown: split on headers.
    for md in sorted(tier_dir.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        header = "(top)"
        body: list[str] = []
        for line in text.splitlines():
            if line.startswith("#"):
                if body:
                    out.append(
                        Chunk(
                            tier=tier_name,
                            source=str(md.name),
                            header=header,
                            text="\n".join(body).strip(),
                        )
                    )
                header = line.strip()
                body = []
            else:
                body.append(line)
        if body:
            out.append(
                Chunk(
                    tier=tier_name, source=str(md.name), header=header, text="\n".join(body).strip()
                )
            )
    # JSONL append-only log (each line = {"text": str, "header": str?})
    for jl in sorted(tier_dir.glob("*.jsonl")):
        try:
            lines = jl.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                Chunk(
                    tier=tier_name,
                    source=str(jl.name),
                    header=rec.get("header", "(entry)"),
                    text=str(rec.get("text", "")).strip(),
                )
            )
    return out


def load_all(project_root: str | os.PathLike) -> list[Chunk]:
    root = Path(project_root).resolve()
    chunks: list[Chunk] = []
    chunks.extend(_load_tier(_user_root(), "user"))
    chunks.extend(_load_tier(_team_root(root), "team"))
    chunks.extend(_load_tier(_project_root(root), "project"))
    return [c for c in chunks if c.text]


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
def retrieve(
    project_root: str | os.PathLike,
    query: str,
    *,
    top_k: int = 8,
    backend: str | None = None,
    tiers: Iterable[str] | None = None,
    lexical_weight: float = 0.5,
) -> list[dict[str, Any]]:
    """Return the top-k chunks ranked by lexical + embedding score.

    ``lexical_weight`` blends the normalised lexical overlap with the
    normalised embedding similarity.  Set to 1.0 to disable embedding
    (pure v0.7 behaviour) or 0.0 for pure embedding.
    """
    root = Path(project_root).resolve()
    emb = get_backend(backend)
    q_tokens = tokenize(query)
    q_emb = emb.embed(query)
    tiers_set = set(tiers) if tiers else set(TIER_PRECEDENCE)

    chunks = [c for c in load_all(root) if c.tier in tiers_set]
    if not chunks:
        return []
    # Lexical scoring (token overlap with log-length normalisation).
    lex_scores: list[float] = []
    for c in chunks:
        tokens = tokenize(c.text + " " + c.header)
        overlap = len(q_tokens & tokens)
        c.overlap = overlap
        if not tokens:
            lex_scores.append(0.0)
        else:
            lex_scores.append(overlap / (1.0 + math.log(1.0 + len(tokens))))
    max_lex = max(lex_scores) or 1.0

    # Embedding scoring (cosine sim).
    emb_scores: list[float] = []
    for c in chunks:
        c_emb = emb.embed(c.text + " " + c.header)
        sim = emb.similarity(q_emb, c_emb)
        c.embedding_score = sim
        emb_scores.append(max(0.0, sim))
    max_emb = max(emb_scores) or 1.0

    # Combine.  A tier-bump gives project a slight edge so team and
    # user facts can be overridden by repo-local statements.
    tier_bump = {"project": 0.05, "team": 0.02, "user": 0.0}
    for i, c in enumerate(chunks):
        lex = lex_scores[i] / max_lex
        embn = emb_scores[i] / max_emb
        c.score = lexical_weight * lex + (1 - lexical_weight) * embn + tier_bump.get(c.tier, 0.0)

    # Deduplicate by (header, text) keeping highest precedence tier.
    seen: dict[tuple[str, str], Chunk] = {}
    for c in chunks:
        k = (c.header, c.text[:200])
        prev = seen.get(k)
        if prev is None or TIER_PRECEDENCE.index(c.tier) < TIER_PRECEDENCE.index(prev.tier):
            seen[k] = c
    uniq = list(seen.values())
    uniq.sort(key=lambda c: c.score, reverse=True)
    return [c.to_dict() for c in uniq[: max(1, top_k)]]


# ---------------------------------------------------------------------------
# Mutations — append JSONL entries
# ---------------------------------------------------------------------------
def add_entry(
    project_root: str | os.PathLike,
    tier: str,
    *,
    text: str,
    header: str = "(entry)",
    source: str = "log.jsonl",
) -> dict[str, Any]:
    """Append a new memory entry to one of the three tiers.

    Writes to ``<tier_dir>/<source>`` (default: ``log.jsonl``).

    ``source`` is restricted to a safe basename (``[A-Za-z0-9._-]+``) so it
    cannot escape the tier directory via ``..`` or absolute paths (v0.10 P1).
    """
    if tier not in TIER_PRECEDENCE:
        raise ValueError(f"unknown tier: {tier}; known: {TIER_PRECEDENCE}")
    if not isinstance(source, str) or not re.match(r"^[A-Za-z0-9._-]+$", source):
        raise ValueError(f"invalid source filename: {source!r} (safe basename required)")
    root = Path(project_root).resolve()
    dirs = {"user": _user_root(), "team": _team_root(root), "project": _project_root(root)}
    tdir = dirs[tier]
    tdir.mkdir(parents=True, exist_ok=True)
    p = tdir / source
    # Defence-in-depth: ensure final path stays inside the tier dir.
    try:
        p.resolve().relative_to(tdir.resolve())
    except ValueError as e:
        raise ValueError(f"source escapes tier directory: {source!r}") from e
    rec = {"ts": time.time(), "header": header, "text": text}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"tier": tier, "source": str(p), "bytes": len(text)}


def tier_stats(project_root: str | os.PathLike) -> dict[str, dict[str, int]]:
    """Return {tier: {files, entries, bytes}} for dashboard / doctor."""
    root = Path(project_root).resolve()
    dirs = {"user": _user_root(), "team": _team_root(root), "project": _project_root(root)}
    out: dict[str, dict[str, int]] = {}
    for tier, d in dirs.items():
        files = entries = bytes_ = 0
        if d.exists():
            for p in list(d.glob("*.md")) + list(d.glob("*.jsonl")):
                files += 1
                bytes_ += p.stat().st_size
                if p.suffix == ".jsonl":
                    with p.open(encoding="utf-8") as f:
                        entries += sum(1 for _ in f)
                else:
                    entries += sum(
                        1 for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("#")
                    )
        out[tier] = {"files": files, "entries": entries, "bytes": bytes_}
    return out
