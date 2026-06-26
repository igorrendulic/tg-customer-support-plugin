from __future__ import annotations

import sqlite3
import sys
from datetime import date
from types import SimpleNamespace

from tg_support.indexing.chunking import chunk_manual_notes, chunk_messages, chunk_pages
from tg_support.indexing.embeddings import BgeM3EmbeddingModel, RetrievalDependencyError
from tg_support.indexing.hybrid import reciprocal_rank_fusion
from tg_support.indexing.vector import SQLiteVecStore
from tg_support.storage.db import DocumentRecord
from tests.conftest import make_test_retriever, seed_messages


def test_hybrid_search_returns_source_references(db):
    seed_messages(db)
    db.upsert_page("https://example.com/passkeys", "Passkeys", "Passkey setup and login troubleshooting guide.")
    chunk_messages(db)
    chunk_pages(db)
    retriever = make_test_retriever(db)
    retriever.build()
    results = retriever.search("passkey login", limit=3)
    assert results
    assert {"chunk_id", "source_type", "source_id", "metadata"} <= set(results[0])


def test_exact_product_policy_terms_with_punctuation_are_recoverable(db):
    db.upsert_page(
        "https://example.com/policy",
        "Policy",
        "The account-transfer_policy requires verified-email before account-transfer_policy can proceed.",
    )
    chunk_pages(db)
    retriever = make_test_retriever(db)
    retriever.build()

    results = retriever.search("account-transfer_policy", limit=3)

    assert results
    assert "account-transfer_policy" in results[0]["text"]


def test_search_with_fts_syntax_punctuation_does_not_crash(db):
    db.upsert_page("https://example.com/policy", "Policy", "Passkey-reset policy.")
    chunk_pages(db)
    retriever = make_test_retriever(db)
    retriever.build()

    results = retriever.search("passkey-reset: policy?", limit=3)

    assert results


def test_sqlite_vec_load_failure_includes_sqlite_version(monkeypatch):
    def fail_load(_conn):
        raise sqlite3.OperationalError("extension loading disabled")

    monkeypatch.setitem(sys.modules, "sqlite_vec", SimpleNamespace(load=fail_load))

    with sqlite3.connect(":memory:") as conn:
        try:
            SQLiteVecStore().load(conn)
        except RetrievalDependencyError as exc:
            assert sqlite3.sqlite_version in str(exc)
            assert "extension loading disabled" in str(exc)
        else:
            raise AssertionError("expected sqlite-vec load failure")


def test_sqlite_vec_search_without_index_returns_no_vector_candidates(monkeypatch, db):
    monkeypatch.setitem(sys.modules, "sqlite_vec", SimpleNamespace(load=lambda _conn: None))

    assert SQLiteVecStore().search(db, [0.1, 0.2], limit=3) == []


def test_bge_model_load_failure_is_structured(monkeypatch):
    class FailingSentenceTransformer:
        def __init__(self, _name):
            raise OSError("model cache unavailable")

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FailingSentenceTransformer))

    try:
        BgeM3EmbeddingModel().embed("hello")
    except RetrievalDependencyError as exc:
        assert "Could not load embedding model BAAI/bge-m3" in str(exc)
    else:
        raise AssertionError("expected structured embedding load failure")


def test_bge_encode_failure_is_structured(monkeypatch):
    class FailingModel:
        def encode(self, *_args, **_kwargs):
            raise RuntimeError("tensor runtime unavailable")

    class SentenceTransformer:
        def __init__(self, _name):
            pass

        def encode(self, *args, **kwargs):
            return FailingModel().encode(*args, **kwargs)

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=SentenceTransformer))

    try:
        BgeM3EmbeddingModel().embed("hello")
    except RetrievalDependencyError as exc:
        assert "Could not encode text with embedding model BAAI/bge-m3" in str(exc)
    else:
        raise AssertionError("expected structured embedding encode failure")


def test_rrf_favors_items_in_both_result_sets():
    one = DocumentRecord(1, 1, "web", 1, 0, "alpha", {}, None)
    two = DocumentRecord(2, 2, "web", 2, 0, "beta", {}, None)
    fused = reciprocal_rank_fusion([[(one, 1.0), (two, 0.5)], [(two, 1.0)]], limit=2)
    assert fused[0][0].id == 2


def test_stale_index_detects_changed_chunks(db):
    seed_messages(db)
    chunk_messages(db)
    retriever = make_test_retriever(db)
    retriever.build()
    assert retriever.stale() is False
    db.upsert_chunk("web", 99, 0, "new text")
    assert retriever.stale() is True


def test_stale_index_detects_in_place_chunk_edits(db):
    db.upsert_page("https://example.com/reset", "Reset", "Reset your password from account settings.")
    chunk_pages(db)
    retriever = make_test_retriever(db)
    retriever.build()
    assert retriever.stale() is False

    page_id = db.upsert_page("https://example.com/reset", "Reset", "Reset your passkey from account settings.")
    db.upsert_chunk("web", page_id, 0, "Reset your passkey from account settings.", {"url": "https://example.com/reset"})

    assert retriever.stale() is True


def test_active_manual_note_ranks_above_older_web_evidence(db):
    db.upsert_page("https://example.com/account-transfer", "Transfer", "Account transfer is available for old email addresses.")
    db.create_manual_note("Account transfer is discontinued. Users must register a new email address.", "2026-04-02")
    chunk_pages(db)
    chunk_manual_notes(db)
    retriever = make_test_retriever(db)
    retriever.build()

    results = retriever.search("account transfer email", as_of=date(2026, 6, 25), limit=2)

    assert results[0]["source_type"] == "manual"
    assert results[0]["metadata"]["effective_date"] == "2026-04-02"


def test_inactive_manual_notes_are_excluded_from_current_search(db):
    db.create_manual_note("Passkey setup policy changes next year.", "2027-01-01")
    db.create_manual_note("Discount policy expired.", "2026-01-01", expires_date="2026-02-01")
    chunk_manual_notes(db)
    retriever = make_test_retriever(db)
    retriever.build()

    results = retriever.search("policy", as_of=date(2026, 6, 25), limit=5)

    assert results == []
