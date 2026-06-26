from __future__ import annotations

import pytest

from tg_support.indexing.embeddings import EmbeddingModel
from tg_support.indexing.hybrid import HybridRetriever
from tg_support.storage.db import DocumentRecord, SupportDatabase


class FakeEmbeddingModel(EmbeddingModel):
    name = "BAAI/bge-small-en-v1.5"

    def embed(self, text: str) -> list[float]:
        base = float(len(text.strip()) or 1)
        return [base, 1.0, 0.0]


class EmptyVectorStore:
    def rebuild(self, _db: SupportDatabase, rows) -> None:
        for _document_id, _vector in rows:
            pass

    def search(self, _db: SupportDatabase, _query_vector: list[float], limit: int = 10) -> list[tuple[DocumentRecord, float]]:
        return []


@pytest.fixture
def db(tmp_path):
    database = SupportDatabase(tmp_path / "support.sqlite3")
    database.initialize()
    return database


def seed_messages(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "alice",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "I cannot reset my password",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 2,
            "author_id": 11,
            "author_username": "helper",
            "sent_at": "2026-06-01T12:01:00Z",
            "text": "Use https://example.com/reset to reset your password",
            "reply_to_message_id": 1,
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 3,
            "author_id": 12,
            "author_username": "bob",
            "sent_at": "2026-06-02T12:00:00Z",
            "text": "Login passkey setup is confusing",
        },
    )
    return chat_id


def make_test_retriever(db: SupportDatabase) -> HybridRetriever:
    return HybridRetriever(db, embedding_model=FakeEmbeddingModel(), vector_store=EmptyVectorStore())


def patch_test_retriever(monkeypatch) -> None:
    class TestHybridRetriever(HybridRetriever):
        def __init__(self, db, *args, **kwargs):
            super().__init__(db, embedding_model=FakeEmbeddingModel(), vector_store=EmptyVectorStore())

    monkeypatch.setattr("tg_support.cli.HybridRetriever", TestHybridRetriever)
    monkeypatch.setattr("tg_support.support.context.HybridRetriever", TestHybridRetriever)
