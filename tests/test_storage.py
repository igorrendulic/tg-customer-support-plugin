from __future__ import annotations

from tg_support.indexing.chunking import chunk_messages, chunk_pages
from tg_support.storage.schema import CURRENT_SCHEMA_VERSION
from tests.conftest import seed_messages


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


def test_index_run_does_not_delete_source_records(db):
    seed_messages(db)
    chunk_messages(db)
    before = db.count("messages")
    db.record_index_run("local-hash-v1", "hybrid-v1")
    assert db.count("messages") == before
