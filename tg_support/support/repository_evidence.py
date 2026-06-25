from __future__ import annotations

import re
from pathlib import Path

from tg_support.repository import RepositoryManager


SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "dist", "build"}
STOPWORDS = {"a", "an", "as", "at", "be", "by", "in", "is", "it", "of", "on", "or", "to"}
TEXT_EXTENSIONS = {
    ".go",
    ".js",
    ".jsx",
    ".md",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".html",
    ".css",
}


def repository_evidence(manager: RepositoryManager, query: str, limit: int = 6) -> dict:
    state = manager.prepare()
    payload = {
        "configured": state.configured,
        "available": state.available,
        "stale": state.stale,
        "warning": state.warning,
        "error": state.error,
        "branch": state.branch,
        "revision": state.revision,
        "evidence": [],
    }
    if not state.available or state.checkout_path is None:
        return payload
    payload["evidence"] = search_checkout(state.checkout_path, query, limit=limit, revision=state.revision, branch=state.branch)
    return payload


def search_checkout(checkout_path: Path, query: str, limit: int, revision: str | None, branch: str | None) -> list[dict]:
    terms = _search_terms(query)
    if not terms:
        return []
    matches = []
    for path in _iter_text_files(checkout_path):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        lowered = text.lower()
        score = sum(lowered.count(term) for term in terms)
        if score <= 0:
            continue
        lines = text.splitlines()
        first = _first_matching_line(lines, terms)
        start = max(1, first - 2)
        end = min(len(lines), first + 2)
        excerpt = "\n".join(lines[start - 1 : end])
        matches.append(
            {
                "source_type": "repository",
                "path": str(path.relative_to(checkout_path)),
                "line_start": start,
                "line_end": end,
                "excerpt": excerpt,
                "score": score,
                "revision": revision,
                "branch": branch,
            }
        )
    return sorted(matches, key=lambda item: (-item["score"], item["path"]))[:limit]


def _search_terms(query: str) -> list[str]:
    terms = []
    for token in re.findall(r"[A-Za-z0-9_]+", query):
        term = token.lower()
        if len(term) > 2 or term not in STOPWORDS:
            terms.append(term)
    return terms


def _iter_text_files(root: Path):
    resolved_root = root.resolve()
    for path in root.rglob("*"):
        parent_parts = path.relative_to(root).parts[:-1]
        if any(part in SKIP_DIRS or part.startswith(".") for part in parent_parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        try:
            path.resolve().relative_to(resolved_root)
        except ValueError:
            continue
        if path.name.startswith(".") or path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        yield path


def _first_matching_line(lines: list[str], terms: list[str]) -> int:
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        if any(term in lowered for term in terms):
            return index
    return 1
