from __future__ import annotations

from tg_support.indexing.chunking import chunk_messages, chunk_pages
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
