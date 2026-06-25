from __future__ import annotations

import re
from collections import Counter

from tg_support.storage.db import ChunkRecord


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*", re.I)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def lexical_search(chunks: list[ChunkRecord], query: str, limit: int = 10) -> list[tuple[ChunkRecord, float]]:
    q = Counter(tokenize(query))
    if not q:
        return []
    scored = []
    for chunk in chunks:
        terms = Counter(tokenize(chunk.text))
        score = sum(min(terms[t], q[t]) for t in q)
        if score:
            scored.append((chunk, float(score)))
    return sorted(scored, key=lambda item: (-item[1], item[0].id))[:limit]
