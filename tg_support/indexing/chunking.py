from __future__ import annotations

from tg_support.storage.db import SupportDatabase


class TranslationHelper:
    def translate_to_english(self, text: str, source_language: str) -> str | None:
        return None


def infer_language(text: str) -> str | None:
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return "zh"
    if any("\u0600" <= char <= "\u06ff" for char in text):
        return "ar"
    if any(char.isalpha() for char in text):
        return "en"
    return None


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
        pages = conn.execute("SELECT id, url, title, text, fetched_at FROM pages WHERE status = 'ok' AND length(text) > 0").fetchall()
    for page in pages:
        for ordinal, text in enumerate(split_text(page["text"])):
            rows.append(("web", page["id"], ordinal, text, {"url": page["url"], "title": page["title"], "fetched_at": page["fetched_at"]}))
    return db.upsert_chunks(rows)


def chunk_manual_notes(db: SupportDatabase) -> int:
    rows = []
    for note in db.manual_notes():
        text_parts = [note.text]
        if note.caveats:
            text_parts.append(f"Caveats: {note.caveats}")
        text = "\n".join(text_parts)
        for ordinal, chunk_text in enumerate(split_text(text)):
            rows.append(
                (
                    "manual",
                    note.id,
                    ordinal,
                    chunk_text,
                    {
                        "note_id": note.id,
                        "effective_date": note.effective_date,
                        "expires_date": note.expires_date,
                        "caveats": note.caveats,
                        "created_at": note.created_at,
                    },
                )
            )
    return db.upsert_chunks(rows)


def chunk_messages(db: SupportDatabase, window: int = 3, translation_helper: TranslationHelper | None = None) -> int:
    chunks = []
    rows = db.telegram_message_author_rows()
    helper = translation_helper or TranslationHelper()
    for index, row in enumerate(rows):
        neighbors = rows[max(0, index - window) : min(len(rows), index + window + 1)]
        lines = [f"{n['author_label']}: {n['text'].strip()}" for n in neighbors if n["text"].strip()]
        text = "\n".join(lines)
        if not text:
            continue
        metadata = {
            "chat": row["chat"],
            "message_id": row["telegram_message_id"],
            "author": row["author_label"],
            "sent_at": row["sent_at"],
        }
        source_language = infer_language(row["text"])
        if source_language is not None:
            metadata["source_language"] = source_language
        if source_language and source_language != "en" and row["text"].strip():
            translated = helper.translate_to_english(row["text"], source_language)
            if translated:
                metadata["translated_text"] = translated
        chunks.append(
            (
                "telegram",
                row["id"],
                0,
                text,
                metadata,
            )
        )
    return db.upsert_chunks(chunks)
