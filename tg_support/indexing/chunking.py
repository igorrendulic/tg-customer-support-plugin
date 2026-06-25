from __future__ import annotations

from tg_support.storage.db import SupportDatabase


def split_text(text: str, max_words: int = 180, overlap: int = 30) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, max_words - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + max_words])
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks


def chunk_pages(db: SupportDatabase) -> int:
    rows = []
    with db.connect() as conn:
        pages = conn.execute("SELECT id, url, title, text FROM pages WHERE status = 'ok' AND length(text) > 0").fetchall()
    for page in pages:
        for ordinal, text in enumerate(split_text(page["text"])):
            rows.append(("web", page["id"], ordinal, text, {"url": page["url"], "title": page["title"]}))
    return db.upsert_chunks(rows)


def chunk_messages(db: SupportDatabase, window: int = 3) -> int:
    chunks = []
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.telegram_message_id, m.author_username, m.sent_at, m.text, c.input AS chat
            FROM messages m JOIN chats c ON c.id = m.chat_id
            ORDER BY m.chat_id, m.telegram_message_id
            """
        ).fetchall()
    for index, row in enumerate(rows):
        neighbors = rows[max(0, index - window) : min(len(rows), index + window + 1)]
        text = "\n".join(f"{n['author_username'] or 'unknown'}: {n['text']}" for n in neighbors)
        chunks.append(
            (
                "telegram",
                row["id"],
                0,
                text,
                {"chat": row["chat"], "message_id": row["telegram_message_id"], "author": row["author_username"], "sent_at": row["sent_at"]},
            )
        )
    return db.upsert_chunks(chunks)
