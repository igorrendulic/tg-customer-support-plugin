from __future__ import annotations

import re

from tg_support.storage.db import DocumentRecord, SupportDatabase


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*", re.I)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def fts_query(query: str) -> str:
    tokens = tokenize(query)
    if not tokens:
        return ""
    return " OR ".join(f'"{token}"' for token in tokens)


def lexical_search(db: SupportDatabase, query: str, limit: int = 10) -> list[tuple[DocumentRecord, float]]:
    compiled = fts_query(query)
    if not compiled:
        return []
    return db.search_fts(compiled, limit)
