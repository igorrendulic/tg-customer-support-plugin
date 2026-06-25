from __future__ import annotations

from datetime import date

from tg_support.indexing.chunking import chunk_manual_notes, chunk_messages, chunk_pages
from tg_support.indexing.hybrid import HybridRetriever, reciprocal_rank_fusion
from tg_support.storage.db import ChunkRecord
from tests.conftest import seed_messages


def test_hybrid_search_returns_source_references(db):
    seed_messages(db)
    db.upsert_page("https://example.com/passkeys", "Passkeys", "Passkey setup and login troubleshooting guide.")
    chunk_messages(db)
    chunk_pages(db)
    retriever = HybridRetriever(db)
    retriever.build()
    results = retriever.search("passkey login", limit=3)
    assert results
    assert {"chunk_id", "source_type", "source_id", "metadata"} <= set(results[0])


def test_rrf_favors_items_in_both_result_sets():
    one = ChunkRecord(1, "web", 1, 0, "alpha", {})
    two = ChunkRecord(2, "web", 2, 0, "beta", {})
    fused = reciprocal_rank_fusion([[(one, 1.0), (two, 0.5)], [(two, 1.0)]], limit=2)
    assert fused[0][0].id == 2


def test_stale_index_detects_changed_chunks(db):
    seed_messages(db)
    chunk_messages(db)
    retriever = HybridRetriever(db)
    retriever.build()
    assert retriever.stale() is False
    db.upsert_chunk("web", 99, 0, "new text")
    assert retriever.stale() is True


def test_active_manual_note_ranks_above_older_web_evidence(db):
    db.upsert_page("https://example.com/account-transfer", "Transfer", "Account transfer is available for old email addresses.")
    db.create_manual_note("Account transfer is discontinued. Users must register a new email address.", "2026-04-02")
    chunk_pages(db)
    chunk_manual_notes(db)
    retriever = HybridRetriever(db)
    retriever.build()

    results = retriever.search("account transfer email", as_of=date(2026, 6, 25), limit=2)

    assert results[0]["source_type"] == "manual"
    assert results[0]["metadata"]["effective_date"] == "2026-04-02"


def test_inactive_manual_notes_are_excluded_from_current_search(db):
    db.create_manual_note("Passkey setup policy changes next year.", "2027-01-01")
    db.create_manual_note("Discount policy expired.", "2026-01-01", expires_date="2026-02-01")
    chunk_manual_notes(db)
    retriever = HybridRetriever(db)
    retriever.build()

    results = retriever.search("policy", as_of=date(2026, 6, 25), limit=5)

    assert results == []
