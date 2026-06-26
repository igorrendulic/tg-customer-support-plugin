from __future__ import annotations

import re

from tg_support.indexing.hybrid import HybridRetriever
from tg_support.storage.db import SupportDatabase

STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "but",
    "can",
    "for",
    "from",
    "has",
    "have",
    "how",
    "into",
    "need",
    "not",
    "our",
    "please",
    "should",
    "that",
    "the",
    "their",
    "them",
    "this",
    "user",
    "users",
    "what",
    "when",
    "where",
    "with",
    "you",
    "your",
}

PRIVATE_DETAIL_PATTERNS = (
    r"\baccount\b",
    r"\baccount email\b",
    r"\bbilling\b",
    r"\binvoice\b",
    r"\bpayment\b",
    r"\bsubscription\b",
    r"\bemail address\b",
    r"\buser id\b",
    r"\bworkspace\b",
    r"\borganization\b",
    r"\borg\b",
    r"\blogs?\b",
    r"\bscreenshot\b",
    r"\berror code\b",
    r"\bapi key\b",
)

MISSING_DETAIL_PATTERNS = (
    r"\bneed\b.*\b(info|information|details?|email|logs?|screenshot|user id|account)\b",
    r"\bask\b.*\b(info|information|details?|email|logs?|screenshot|user id|account)\b",
    r"\bmore\b.*\b(info|information|details?)\b",
    r"\bcan't\b.*\bwithout\b",
    r"\bcannot\b.*\bwithout\b",
)


def user_history(db: SupportDatabase, username: str, limit: int = 5) -> list[dict]:
    normalized = username.lstrip("@")
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT telegram_message_id, author_username, sent_at, text, reply_to_message_id
            FROM messages
            WHERE author_username = ?
            ORDER BY sent_at DESC LIMIT ?
            """,
            (normalized, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def message_context(db: SupportDatabase, message_id: int, window: int = 3) -> list[dict]:
    with db.connect() as conn:
        target = conn.execute("SELECT chat_id, telegram_message_id FROM messages WHERE telegram_message_id = ?", (message_id,)).fetchone()
        if target is None:
            return []
        rows = conn.execute(
            """
            SELECT telegram_message_id, author_username, sent_at, text, reply_to_message_id
            FROM messages
            WHERE chat_id = ? AND telegram_message_id BETWEEN ? AND ?
            ORDER BY telegram_message_id
            """,
            (target["chat_id"], target["telegram_message_id"] - window, target["telegram_message_id"] + window),
        ).fetchall()
    return [dict(row) for row in rows]


def content_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9][a-z0-9_-]*", text.lower())
        if len(word) > 2 and word not in STOP_WORDS
    }


def account_specific_gap(
    query: str,
    thread: list[dict],
    history: list[dict],
    evidence: list[dict],
    has_limiting_reason: bool,
) -> bool:
    text = " ".join(
        [query, *(item.get("text") or "" for item in thread), *(item.get("text") or "" for item in history)]
    ).lower()
    if not text:
        return False
    has_private_detail = any(re.search(pattern, text) for pattern in PRIVATE_DETAIL_PATTERNS)
    asks_for_missing_detail = any(re.search(pattern, text) for pattern in MISSING_DETAIL_PATTERNS)
    return has_private_detail and (asks_for_missing_detail or has_limiting_reason or not evidence)


def weak_evidence(query: str, evidence: list[dict]) -> bool:
    if not query.strip() or not evidence:
        return False
    query_words = content_words(query)
    if not query_words:
        return False
    evidence_words = set().union(*(content_words(item.get("text") or "") for item in evidence))
    return not bool(query_words & evidence_words)


def evidence_sufficiency(
    query: str,
    evidence: list[dict],
    conflicts: list[dict],
    history: list[dict],
    thread: list[dict],
    username: str | None,
) -> dict:
    reasons = []
    if not evidence:
        reasons.append(
            {
                "code": "no_evidence",
                "message": "No relevant local evidence was returned for this draft request.",
            }
        )
    elif weak_evidence(query, evidence):
        reasons.append(
            {
                "code": "weak_evidence",
                "message": "Returned evidence has weak lexical overlap with the draft request.",
            }
        )
    if conflicts:
        reasons.append(
            {
                "code": "conflicting_evidence",
                "message": "Manual Knowledge conflicts require operator review before treating the answer as settled.",
            }
        )
    if username and not history:
        reasons.append(
            {
                "code": "missing_user_history",
                "message": "No local history was found for the target user.",
            }
        )
    if account_specific_gap(query, thread, history, evidence, bool(reasons)):
        reasons.append(
            {
                "code": "account_specific_gap",
                "message": "The draft may need private or account-specific details that are not present in the evidence.",
            }
        )
    state = "insufficient" if reasons else "direct_answerable"
    return {
        "state": state,
        "direct_answer_supported": state == "direct_answerable",
        "fallback_recommended": state == "insufficient",
        "reasons": reasons,
    }


def draft_context(
    db: SupportDatabase,
    query: str,
    username: str | None = None,
    message_id: int | None = None,
    limit: int = 6,
    retriever: HybridRetriever | None = None,
) -> dict:
    target_history = user_history(db, username, limit=limit) if username else []
    thread = message_context(db, message_id) if message_id is not None else []
    search_query = query or " ".join(item["text"] for item in (thread or target_history))
    retriever = retriever or HybridRetriever(db)
    search = retriever.search_with_conflicts(search_query, limit=limit)
    suggestion = None
    if username and not target_history:
        suggestion = "No local history for this user. Run sync, search by message ID, or broaden the query."
    sufficiency = evidence_sufficiency(
        search_query,
        search["evidence"],
        search["conflicts"],
        target_history,
        thread,
        username,
    )
    return {
        "target": {"username": username, "message_id": message_id},
        "history": target_history,
        "thread": thread,
        "evidence": search["evidence"],
        "conflicts": search["conflicts"],
        "evidence_sufficiency": sufficiency,
        "suggestion": suggestion,
    }
