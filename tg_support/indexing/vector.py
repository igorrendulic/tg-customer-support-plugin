from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from typing import Protocol

from tg_support.indexing.embeddings import BgeEmbeddingModel, EmbeddingModel, RetrievalDependencyError
from tg_support.storage.db import DocumentRecord, SupportDatabase


class VectorStore(Protocol):
    def rebuild(self, db: SupportDatabase, rows: Iterable[tuple[int, list[float]]]) -> None:
        ...

    def search(self, db: SupportDatabase, query_vector: list[float], limit: int = 10) -> list[tuple[DocumentRecord, float]]:
        ...


class SQLiteVecStore:
    def __init__(self, dims: int = 384):
        self.dims = dims

    def load(self, conn: sqlite3.Connection) -> None:
        try:
            import sqlite_vec
        except ImportError as exc:
            raise RetrievalDependencyError("Missing sqlite-vec dependency. Install the retrieval extra and rebuild the index.") from exc
        try:
            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except sqlite3.Error as exc:
            raise RetrievalDependencyError(f"Could not load sqlite-vec with SQLite {sqlite3.sqlite_version}: {exc}") from exc
        finally:
            try:
                conn.enable_load_extension(False)
            except sqlite3.Error:
                pass

    def initialize(self, conn: sqlite3.Connection) -> None:
        self.load(conn)
        self.create_table(conn)

    def create_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_documents USING vec0(embedding float[{self.dims}])"
        )

    def rebuild(self, db: SupportDatabase, rows: Iterable[tuple[int, list[float]]]) -> None:
        payload = [(document_id, json.dumps(vector)) for document_id, vector in rows]
        with db.connect() as conn:
            self.load(conn)
            conn.execute("DROP TABLE IF EXISTS vec_documents")
            self.create_table(conn)
            conn.executemany("INSERT INTO vec_documents(rowid, embedding) VALUES (?, ?)", payload)

    def search(self, db: SupportDatabase, query_vector: list[float], limit: int = 10) -> list[tuple[DocumentRecord, float]]:
        with db.connect() as conn:
            self.load(conn)
            try:
                rows = conn.execute(
                    """
                    SELECT rowid AS document_id, distance
                    FROM vec_documents
                    WHERE embedding MATCH ?
                    ORDER BY distance
                    LIMIT ?
                    """,
                    (json.dumps(query_vector), limit),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table: vec_documents" in str(exc):
                    return []
                raise
        documents = db.documents_by_id(int(row["document_id"]) for row in rows)
        return [(documents[int(row["document_id"])], float(row["distance"])) for row in rows if int(row["document_id"]) in documents]


class VectorSearcher:
    def __init__(self, db: SupportDatabase, model: EmbeddingModel | None = None, store: VectorStore | None = None):
        self.db = db
        self.model = model or BgeEmbeddingModel()
        self.store = store or SQLiteVecStore()

    def rebuild(self, documents: list[DocumentRecord]) -> None:
        self.store.rebuild(self.db, ((document.id, self.model.embed(document.text)) for document in documents))

    def search(self, query: str, limit: int = 10) -> list[tuple[DocumentRecord, float]]:
        query_vec = self.model.embed(query)
        return self.store.search(self.db, query_vec, limit)
