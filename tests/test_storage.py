from __future__ import annotations

from tg_support.indexing.chunking import chunk_messages, chunk_pages
from tg_support.storage.db import SupportDatabase
from tg_support.storage.schema import CURRENT_SCHEMA_VERSION
from tests.conftest import seed_display_name_author_messages, seed_messages


def test_database_initialization_is_idempotent(db):
    db.initialize()
    assert db.schema_version() == CURRENT_SCHEMA_VERSION


def test_chunk_records_trace_to_sources(db):
    seed_messages(db)
    page_id = db.upsert_page("https://example.com/reset", "Reset", "Reset your password from account settings.")
    chunk_messages(db)
    chunk_pages(db)
    chunks = db.chunks()
    assert {chunk.source_type for chunk in chunks} == {"telegram", "web"}
    web = next(chunk for chunk in chunks if chunk.source_type == "web")
    assert web.source_id == page_id
    assert web.metadata["url"] == "https://example.com/reset"


def test_manual_note_records_trace_to_chunks(db):
    note_id = db.create_manual_note(
        "Account transfers were discontinued. Users must register a new email.",
        "2026-04-02",
        caveats="Old email addresses are quarantined.",
    )
    db.upsert_chunk("manual", note_id, 0, "Account transfers were discontinued.", {"note_id": note_id, "effective_date": "2026-04-02"})

    notes = db.manual_notes()
    chunks = db.chunks()

    assert notes[0].text.startswith("Account transfers")
    assert notes[0].effective_date == "2026-04-02"
    assert notes[0].caveats == "Old email addresses are quarantined."
    assert chunks[0].source_type == "manual"
    assert chunks[0].source_id == note_id
    assert chunks[0].metadata["effective_date"] == "2026-04-02"


def test_index_run_does_not_delete_source_records(db):
    seed_messages(db)
    chunk_messages(db)
    before = db.count("messages")
    db.record_index_run("BAAI/bge-small-en-v1.5", "sqlite-hybrid-v1")
    assert db.count("messages") == before
    assert db.latest_index_run("BAAI/bge-small-en-v1.5")["source_signature"] == db.chunk_signature()


def test_rebuild_documents_preserves_source_metadata(db):
    seed_messages(db)
    page_id = db.upsert_page("https://example.com/account-transfer", "Transfer", "Account-transfer_policy details.")
    chunk_messages(db)
    chunk_pages(db)

    documents = db.rebuild_documents()

    assert db.count("documents") == len(db.chunks())
    web = next(document for document in documents if document.source_type == "web")
    assert web.source_id == page_id
    assert web.metadata["url"] == "https://example.com/account-transfer"
    assert db.search_fts('"account-transfer_policy"', 3)[0][0].id == web.id


def test_message_author_rows_use_display_name_when_username_missing(db):
    seed_display_name_author_messages(db)

    rows = db.telegram_message_author_rows()

    display_name = next(row for row in rows if row["telegram_message_id"] == 2)
    unknown = next(row for row in rows if row["telegram_message_id"] == 3)
    assert display_name["author_label"] == "crinx7"
    assert display_name["author_username"] is None
    assert display_name["author_display_name"] == "crinx7"
    assert unknown["author_label"] == "unknown"


def test_telegram_author_documents_match_display_name_when_username_missing(db):
    seed_display_name_author_messages(db)
    chunk_messages(db, window=0)
    db.rebuild_documents()

    documents = db.telegram_documents_by_author_username("crinx7")

    assert documents
    assert documents[0].metadata["author"] == "crinx7"
    assert "email already exist" in documents[0].text


def test_telegram_author_documents_match_display_name_when_username_empty(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "",
            "author_name": "crinx7",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "It says email already exist",
        },
    )
    chunk_messages(db, window=0)
    db.rebuild_documents()

    documents = db.telegram_documents_by_author_username("@crinx7")

    assert documents
    assert documents[0].metadata["author"] == "crinx7"


def test_rebuild_documents_indexes_translation_without_replacing_text(db):
    chunk_id = db.upsert_chunk(
        "telegram",
        1,
        0,
        "yonghengyige: 刚申请一个邮箱",
        {"translated_text": "just applied for a mailbox"},
    )

    documents = db.rebuild_documents()

    document = documents[0]
    assert document.chunk_id == chunk_id
    assert document.text == "yonghengyige: 刚申请一个邮箱"
    assert db.search_fts('"mailbox"', 3)[0][0].id == document.id


def test_initialize_migrates_v1_chunks_to_manual_source_type(tmp_path):
    path = tmp_path / "support.sqlite3"
    db = SupportDatabase(path)
    with db.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO schema_version(version) VALUES (1);
            CREATE TABLE chunks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_type TEXT NOT NULL CHECK(source_type IN ('telegram','web')),
              source_id INTEGER NOT NULL,
              ordinal INTEGER NOT NULL,
              text TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(source_type, source_id, ordinal)
            );
            INSERT INTO chunks(source_type, source_id, ordinal, text) VALUES ('web', 1, 0, 'legacy text');
            CREATE TABLE lexical_refs (
              chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
              terms_json TEXT NOT NULL
            );
            CREATE TABLE vector_refs (
              chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
              embedding_model TEXT NOT NULL,
              vector_json TEXT NOT NULL
            );
            INSERT INTO lexical_refs(chunk_id, terms_json) VALUES (1, '["legacy"]');
            INSERT INTO vector_refs(chunk_id, embedding_model, vector_json) VALUES (1, 'legacy-prototype', '[1.0]');
            """
        )

    db.initialize()
    note_id = db.create_manual_note("New policy", "2026-04-02")
    db.upsert_chunk("manual", note_id, 0, "New policy")

    assert db.schema_version() == CURRENT_SCHEMA_VERSION
    assert {chunk.source_type for chunk in db.chunks()} == {"web", "manual"}
    assert {document.source_type for document in db.rebuild_documents()} == {"web", "manual"}
