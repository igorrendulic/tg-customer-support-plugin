from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tg_support.storage.schema import CURRENT_SCHEMA_VERSION, SCHEMA_SQL


@dataclass(frozen=True)
class ChunkRecord:
    id: int
    source_type: str
    source_id: int
    ordinal: int
    text: str
    metadata: dict[str, Any]


class SupportDatabase:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO schema_version(version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )

    def schema_version(self) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT MAX(version) AS version FROM schema_version").fetchone()
            return None if row is None else row["version"]

    def upsert_chat(self, chat_input: str, telegram_id: str | None = None, title: str | None = None, type_: str | None = None) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chats(input, telegram_id, title, type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(input) DO UPDATE SET
                  telegram_id=excluded.telegram_id,
                  title=excluded.title,
                  type=excluded.type,
                  resolved_at=CURRENT_TIMESTAMP
                """,
                (chat_input, telegram_id, title, type_),
            )
            return int(conn.execute("SELECT id FROM chats WHERE input = ?", (chat_input,)).fetchone()["id"])

    def upsert_user(self, telegram_id: str | None, username: str | None, display_name: str | None = None) -> int | None:
        if telegram_id is None and username is None:
            return None
        key = telegram_id or f"username:{username}"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO users(telegram_id, username, display_name)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                  username=excluded.username,
                  display_name=excluded.display_name
                """,
                (key, username, display_name),
            )
            return int(conn.execute("SELECT id FROM users WHERE telegram_id = ?", (key,)).fetchone()["id"])

    def insert_message(self, chat_id: int, message: dict[str, Any]) -> int:
        author_id = self.upsert_user(
            str(message["author_id"]) if message.get("author_id") is not None else None,
            message.get("author_username"),
            message.get("author_name"),
        )
        source_ref = f"tg:{chat_id}:{message['message_id']}"
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages(chat_id, telegram_message_id, author_id, author_username, sent_at, text, reply_to_message_id, source_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_ref) DO UPDATE SET
                  author_id=excluded.author_id,
                  author_username=excluded.author_username,
                  sent_at=excluded.sent_at,
                  text=excluded.text,
                  reply_to_message_id=excluded.reply_to_message_id
                """,
                (
                    chat_id,
                    message["message_id"],
                    author_id,
                    message.get("author_username"),
                    message["sent_at"],
                    message.get("text") or "",
                    message.get("reply_to_message_id"),
                    source_ref,
                ),
            )
            return int(conn.execute("SELECT id FROM messages WHERE source_ref = ?", (source_ref,)).fetchone()["id"])

    def upsert_page(self, url: str, title: str | None, text: str, rendered: bool = False, status: str = "ok", error: str | None = None) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pages(url, title, text, rendered, status, error)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                  title=excluded.title,
                  text=excluded.text,
                  fetched_at=CURRENT_TIMESTAMP,
                  rendered=excluded.rendered,
                  status=excluded.status,
                  error=excluded.error
                """,
                (url, title, text, int(rendered), status, error),
            )
            return int(conn.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()["id"])

    def upsert_chunk(self, source_type: str, source_id: int, ordinal: int, text: str, metadata: dict[str, Any] | None = None) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO chunks(source_type, source_id, ordinal, text, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_id, ordinal) DO UPDATE SET
                  text=excluded.text,
                  metadata_json=excluded.metadata_json
                """,
                (source_type, source_id, ordinal, text, json.dumps(metadata or {}, sort_keys=True)),
            )
            row = conn.execute(
                "SELECT id FROM chunks WHERE source_type = ? AND source_id = ? AND ordinal = ?",
                (source_type, source_id, ordinal),
            ).fetchone()
            return int(row["id"])

    def upsert_chunks(self, rows: Iterable[tuple[str, int, int, str, dict[str, Any] | None]]) -> int:
        payload = [
            (source_type, source_id, ordinal, text, json.dumps(metadata or {}, sort_keys=True))
            for source_type, source_id, ordinal, text, metadata in rows
        ]
        if not payload:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO chunks(source_type, source_id, ordinal, text, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_id, ordinal) DO UPDATE SET
                  text=excluded.text,
                  metadata_json=excluded.metadata_json
                """,
                payload,
            )
        return len(payload)

    def chunks(self) -> list[ChunkRecord]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM chunks ORDER BY id").fetchall()
        return [
            ChunkRecord(row["id"], row["source_type"], row["source_id"], row["ordinal"], row["text"], json.loads(row["metadata_json"]))
            for row in rows
        ]

    def count(self, table: str) -> int:
        if table not in {"chats", "users", "messages", "pages", "chunks", "index_runs", "drafts", "confirmations", "post_attempts"}:
            raise ValueError("Unsupported table")
        with self.connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])

    def max_chunk_id(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM chunks").fetchone()["max_id"])

    def record_index_run(self, embedding_model: str, index_version: str, status: str = "ok") -> int:
        with self.connect() as conn:
            max_chunk = conn.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM chunks").fetchone()["max_id"]
            cur = conn.execute(
                "INSERT INTO index_runs(embedding_model, index_version, source_max_chunk_id, status) VALUES (?, ?, ?, ?)",
                (embedding_model, index_version, max_chunk, status),
            )
            return int(cur.lastrowid)

    def latest_index_run(self, embedding_model: str) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM index_runs WHERE embedding_model = ? ORDER BY id DESC LIMIT 1",
                (embedding_model,),
            ).fetchone()

    def save_lexical_terms(self, chunk_id: int, terms: Iterable[str]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO lexical_refs(chunk_id, terms_json) VALUES (?, ?)",
                (chunk_id, json.dumps(list(terms), sort_keys=True)),
            )

    def save_vector(self, chunk_id: int, embedding_model: str, vector: list[float]) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO vector_refs(chunk_id, embedding_model, vector_json) VALUES (?, ?, ?)",
                (chunk_id, embedding_model, json.dumps(vector)),
            )

    def save_index_entries(self, lexical_rows: Iterable[tuple[int, Iterable[str]]], vector_rows: Iterable[tuple[int, str, list[float]]]) -> None:
        with self.connect() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO lexical_refs(chunk_id, terms_json) VALUES (?, ?)",
                [(chunk_id, json.dumps(list(terms), sort_keys=True)) for chunk_id, terms in lexical_rows],
            )
            conn.executemany(
                "INSERT OR REPLACE INTO vector_refs(chunk_id, embedding_model, vector_json) VALUES (?, ?, ?)",
                [(chunk_id, model, json.dumps(vector)) for chunk_id, model, vector in vector_rows],
            )
