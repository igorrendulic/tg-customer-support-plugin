from __future__ import annotations

from tg_support.indexing.chunking import TranslationHelper, chunk_manual_notes, chunk_messages, chunk_support_exchanges, split_text
from tg_support.indexing.exchanges import rebuild_support_exchanges
from tests.conftest import seed_display_name_author_messages, seed_messages


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


def test_telegram_chunks_use_display_name_author_labels(db):
    seed_display_name_author_messages(db)

    chunk_messages(db, window=0)

    chunk = next(chunk for chunk in db.chunks() if chunk.metadata["message_id"] == 2)
    assert chunk.metadata["author"] == "crinx7"
    assert chunk.text == "crinx7: It says email already exist"


def test_telegram_chunks_store_all_visible_author_identities(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "helper123",
            "author_name": "Anon",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "I cannot access my mailbox",
        },
    )

    chunk_messages(db, window=0)

    chunk = db.chunks()[0]
    assert chunk.metadata["author"] == "helper123"
    assert chunk.metadata["author_identities"] == ["helper123", "Anon"]
    assert chunk.text == "helper123: I cannot access my mailbox"


def test_telegram_chunks_skip_empty_neighbor_messages(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "yonghengyige",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 2,
            "author_id": 10,
            "author_username": "yonghengyige",
            "sent_at": "2026-06-01T12:01:00Z",
            "text": "管理看到，回复下，谢谢",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 3,
            "author_id": 11,
            "author_username": None,
            "sent_at": "2026-06-01T12:02:00Z",
            "text": "   ",
        },
    )

    chunk_messages(db, window=1)

    chunk = next(chunk for chunk in db.chunks() if chunk.metadata["message_id"] == 2)
    assert chunk.text == "yonghengyige: 管理看到，回复下，谢谢"


class FakeTranslationHelper:
    def translate_to_english(self, text: str, source_language: str) -> str | None:
        assert source_language == "zh"
        assert "刚申请一个邮箱" in text
        return "just applied for a mailbox"


def test_telegram_chunks_store_language_and_translated_helper_context(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "yonghengyige",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "刚申请一个邮箱",
        },
    )

    chunk_messages(db, window=0, translation_helper=FakeTranslationHelper())

    chunk = db.chunks()[0]
    assert chunk.text == "yonghengyige: 刚申请一个邮箱"
    assert chunk.metadata["source_language"] == "zh"
    assert chunk.metadata["translated_text"] == "just applied for a mailbox"


def test_default_translation_helper_does_not_translate(db):
    assert TranslationHelper().translate_to_english("刚申请一个邮箱", "zh") is None


def test_manual_note_chunks_include_validity_metadata(db):
    note_id = db.create_manual_note("Account transfer is discontinued.", "2026-04-02", caveats="Old emails are quarantined.")

    assert chunk_manual_notes(db) == 1

    chunk = db.chunks()[0]
    assert chunk.source_type == "manual"
    assert chunk.source_id == note_id
    assert "Old emails are quarantined" in chunk.text
    assert chunk.metadata["effective_date"] == "2026-04-02"
    assert chunk.metadata["note_id"] == note_id


def test_support_exchange_chunks_include_structured_member_metadata(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "snuglyni",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "Please delete my old account.",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 2,
            "author_id": 11,
            "author_username": "igormailio",
            "sent_at": "2026-06-01T12:01:00Z",
            "text": "We cannot delete it from here.",
            "reply_to_message_id": 1,
        },
    )
    rebuild_support_exchanges(db, ("igormailio",))

    assert chunk_support_exchanges(db) == 1
    chunk = db.chunks()[0]

    assert chunk.source_type == "exchange"
    assert chunk.metadata["status"] == "answered_by_operator"
    assert chunk.metadata["members"][0]["author"] == "snuglyni"
    assert chunk.metadata["members"][0]["role"] == "requester"
    assert chunk.metadata["members"][1]["authority"] == "operator"
    assert "Requester snuglyni: Please delete my old account." in chunk.text
    assert "Operator igormailio: We cannot delete it from here." in chunk.text
