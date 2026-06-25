from __future__ import annotations

from tg_support.indexing.hybrid import HybridRetriever
from tg_support.storage.db import SupportDatabase


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


def draft_context(db: SupportDatabase, query: str, username: str | None = None, message_id: int | None = None, limit: int = 6) -> dict:
    target_history = user_history(db, username, limit=limit) if username else []
    thread = message_context(db, message_id) if message_id is not None else []
    search_query = query or " ".join(item["text"] for item in (thread or target_history))
    evidence = HybridRetriever(db).search(search_query, limit=limit)
    suggestion = None
    if username and not target_history:
        suggestion = "No local history for this user. Run sync, search by message ID, or broaden the query."
    return {
        "target": {"username": username, "message_id": message_id},
        "history": target_history,
        "thread": thread,
        "evidence": evidence,
        "suggestion": suggestion,
    }
