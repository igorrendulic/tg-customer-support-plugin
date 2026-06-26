from __future__ import annotations

from tg_support.indexing.chunking import chunk_messages, chunk_pages
from tg_support.storage.db import ExchangeMemberInput, SupportDatabase, SupportExchangeInput
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


def test_telegram_author_documents_match_display_name_when_username_exists(db):
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
    db.rebuild_documents()

    documents = db.telegram_documents_by_author_username("Anon")

    assert documents
    assert documents[0].metadata["author"] == "helper123"
    assert documents[0].metadata["author_identities"] == ["helper123", "Anon"]


def test_rebuild_documents_indexes_author_identity_terms(db):
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
    db.rebuild_documents()

    document = db.search_fts('"Anon"', 3)[0][0]

    assert document.metadata["author_identities"] == ["helper123", "Anon"]


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


def test_exchange_projection_replaces_rows_idempotently(db):
    chat_id = seed_messages(db)
    with db.connect() as conn:
        requester = conn.execute("SELECT id FROM messages WHERE telegram_message_id = 1").fetchone()["id"]
        operator = conn.execute("SELECT id FROM messages WHERE telegram_message_id = 2").fetchone()["id"]

    exchanges = db.replace_support_exchanges(
        [
            SupportExchangeInput(
                chat_id=chat_id,
                status="answered_by_operator",
                confidence=1.0,
                members=(
                    ExchangeMemberInput(requester, "requester", "none", 0),
                    ExchangeMemberInput(operator, "operator_response", "operator", 1),
                ),
            )
        ]
    )
    replaced = db.replace_support_exchanges(
        [
            SupportExchangeInput(
                chat_id=chat_id,
                status="unanswered",
                confidence=0.5,
                members=(ExchangeMemberInput(requester, "requester", "none", 0),),
            )
        ]
    )

    assert len(exchanges) == 1
    assert len(replaced) == 1
    assert db.count("support_exchanges") == 1
    assert replaced[0].status == "unanswered"
    assert [member.role for member in replaced[0].members] == ["requester"]


def test_exchange_projection_members_trace_to_raw_messages(db):
    chat_id = seed_messages(db)
    with db.connect() as conn:
        requester = conn.execute("SELECT id FROM messages WHERE telegram_message_id = 1").fetchone()["id"]
        peer = conn.execute("SELECT id FROM messages WHERE telegram_message_id = 3").fetchone()["id"]

    db.replace_support_exchanges(
        [
            SupportExchangeInput(
                chat_id=chat_id,
                status="peer_response_only",
                confidence=0.75,
                members=(
                    ExchangeMemberInput(requester, "requester", "none", 0),
                    ExchangeMemberInput(peer, "peer_response", "peer", 1),
                ),
            )
        ]
    )

    exchange = db.support_exchanges()[0]

    assert exchange.members[0].telegram_message_id == 1
    assert exchange.members[0].author == "alice"
    assert exchange.members[1].telegram_message_id == 3
    assert exchange.members[1].role == "peer_response"
    assert exchange.members[1].authority == "peer"


def test_exchange_source_type_is_allowed_in_chunks_and_documents(db):
    chunk_id = db.upsert_chunk("exchange", 1, 0, "Requester: help\nOperator: answer", {"exchange_id": 1})

    documents = db.rebuild_documents()

    assert db.chunks()[0].source_type == "exchange"
    assert documents[0].chunk_id == chunk_id
    assert documents[0].source_type == "exchange"


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


def test_initialize_migrates_v3_to_exchange_projection(tmp_path):
    path = tmp_path / "support.sqlite3"
    db = SupportDatabase(path)
    with db.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE schema_version (
              version INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO schema_version(version) VALUES (3);
            CREATE TABLE chats (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              input TEXT NOT NULL UNIQUE,
              telegram_id TEXT,
              title TEXT,
              type TEXT,
              resolved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              telegram_id TEXT UNIQUE,
              username TEXT,
              display_name TEXT
            );
            CREATE TABLE messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              chat_id INTEGER NOT NULL REFERENCES chats(id),
              telegram_message_id INTEGER NOT NULL,
              author_id INTEGER REFERENCES users(id),
              author_username TEXT,
              sent_at TEXT NOT NULL,
              text TEXT NOT NULL,
              reply_to_message_id INTEGER,
              source_ref TEXT NOT NULL UNIQUE
            );
            CREATE TABLE chunks (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              source_type TEXT NOT NULL CHECK(source_type IN ('telegram','web','manual')),
              source_id INTEGER NOT NULL,
              ordinal INTEGER NOT NULL,
              text TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(source_type, source_id, ordinal)
            );
            CREATE TABLE index_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              embedding_model TEXT NOT NULL,
              index_version TEXT NOT NULL,
              source_max_chunk_id INTEGER NOT NULL,
              source_signature TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE documents (
              id INTEGER PRIMARY KEY,
              chunk_id INTEGER NOT NULL UNIQUE REFERENCES chunks(id) ON DELETE CASCADE,
              source_type TEXT NOT NULL,
              source_id INTEGER NOT NULL,
              ordinal INTEGER NOT NULL,
              text TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              source_updated_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE VIRTUAL TABLE fts_documents USING fts5(
              text,
              content='documents',
              content_rowid='id',
              tokenize = "unicode61 tokenchars '-_'"
            );
            """
        )

    db.initialize()

    assert db.schema_version() == CURRENT_SCHEMA_VERSION
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM support_exchanges").fetchone()["count"] == 0
        create_sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'chunks'").fetchone()["sql"]
    assert "'exchange'" in create_sql
