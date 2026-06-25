from __future__ import annotations

from tg_support.indexing.chunking import chunk_messages, split_text
from tests.conftest import seed_messages


def test_long_webpage_splits_with_stable_ordering():
    chunks = split_text(" ".join(f"word{i}" for i in range(400)), max_words=100, overlap=10)
    assert len(chunks) == 5
    assert chunks[0].startswith("word0")
    assert chunks[1].startswith("word90")


def test_telegram_chunks_include_neighboring_context(db):
    seed_messages(db)
    chunk_messages(db, window=1)
    texts = [chunk.text for chunk in db.chunks()]
    assert any("alice: I cannot reset my password" in text and "helper:" in text for text in texts)
