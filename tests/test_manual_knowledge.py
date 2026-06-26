from __future__ import annotations

import json

from tg_support.cli import main
from tg_support.config import load_config
from tg_support.indexing.chunking import chunk_manual_notes, chunk_messages, chunk_pages
from tg_support.storage.db import SupportDatabase
from tg_support.support.context import draft_context
from tests.conftest import make_test_retriever, patch_test_retriever, seed_messages


def test_knowledge_add_saves_confirmed_note(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()

    code = main(
        [
            "knowledge-add",
            "--text",
            "Account transfers were discontinued. Users must register a new email.",
            "--effective-date",
            "2026-04-02",
            "--caveats",
            "Old email addresses are quarantined.",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    config = load_config(tmp_path / "default" / "config.json")
    notes = SupportDatabase(config.db_path).manual_notes()

    assert code == 0
    assert output["ok"] is True
    assert output["note_id"] == notes[0].id
    assert output["effective_date"] == "2026-04-02"
    assert notes[0].caveats == "Old email addresses are quarantined."


def test_knowledge_add_rejects_invalid_dates_without_writing(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()

    code = main(["knowledge-add", "--text", "Policy changed.", "--effective-date", "2026-04-02", "--expires-date", "2026-04-01"])
    output = json.loads(capsys.readouterr().out)
    config = load_config(tmp_path / "default" / "config.json")

    assert code == 2
    assert output["ok"] is False
    assert "expires_date" in output["error"]
    assert SupportDatabase(config.db_path).manual_notes() == []


def test_no_manual_note_is_saved_when_command_is_not_called(tmp_path, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    config = load_config(tmp_path / "default" / "config.json")

    assert SupportDatabase(config.db_path).manual_notes() == []


def test_draft_context_reports_manual_note_conflicts(db, monkeypatch):
    patch_test_retriever(monkeypatch)
    chat_id = seed_messages(db)
    db.insert_message(
        chat_id,
        {
            "message_id": 4,
            "author_id": 11,
            "author_username": "helper",
            "sent_at": "2026-03-01T12:00:00Z",
            "text": "Account transfer is available for old email addresses.",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 5,
            "author_id": 11,
            "author_username": "helper",
            "sent_at": "2026-04-03T12:00:00Z",
            "text": "Account transfer is discontinued now. Register a new email address.",
        },
    )
    db.upsert_page("https://example.com/transfer", "Transfer", "Account transfer is available for old email addresses.")
    db.create_manual_note("Account transfer is discontinued. Users must register a new email address.", "2026-04-02")
    chunk_messages(db)
    chunk_pages(db)
    chunk_manual_notes(db)
    make_test_retriever(db).build()

    context = draft_context(db, "account transfer email", message_id=5)

    assert context["evidence"][0]["source_type"] == "manual"
    assert context["conflicts"]
    conflict = context["conflicts"][0]
    assert conflict["resolution_required"] is True
    assert conflict["manual_note"]["source_type"] == "manual"
    assert any(item["source_type"] != "manual" for item in conflict["older_evidence"])
    assert any("discontinued now" in item["text"] for item in conflict["fresher_evidence"])


def test_search_outputs_manual_note_evidence_and_conflicts(tmp_path, capsys, monkeypatch):
    patch_test_retriever(monkeypatch)
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    db = SupportDatabase(config.db_path)
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 11,
            "author_username": "helper",
            "sent_at": "2026-03-01T12:00:00Z",
            "text": "Account transfer is available for old email addresses.",
        },
    )
    db.create_manual_note("Account transfer is discontinued. Users must register a new email address.", "2026-04-02")
    chunk_messages(db)
    chunk_manual_notes(db)
    make_test_retriever(db).build()
    capsys.readouterr()

    assert main(["search", "account transfer email"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["results"][0]["source_type"] == "manual"
    assert output["conflicts"][0]["resolution_required"] is True
