from __future__ import annotations

from tg_support.indexing.exchanges import rebuild_support_exchanges


def test_exchange_builder_pairs_operator_reply(db):
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
            "text": "Use the reset page.",
            "reply_to_message_id": 1,
        },
    )

    exchanges = rebuild_support_exchanges(db, ("helper",))

    assert len(exchanges) == 1
    assert exchanges[0].status == "answered_by_operator"
    assert [(member.role, member.authority, member.author) for member in exchanges[0].members] == [
        ("requester", "none", "alice"),
        ("operator_response", "operator", "helper"),
    ]


def test_exchange_builder_keeps_peer_and_operator_responses_separate(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "alice",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "Can I recover my account?",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 2,
            "author_id": 12,
            "author_username": "bob",
            "sent_at": "2026-06-01T12:01:00Z",
            "text": "Try clearing cookies.",
            "reply_to_message_id": 1,
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 3,
            "author_id": 11,
            "author_username": "helper",
            "sent_at": "2026-06-01T12:02:00Z",
            "text": "Officially, recovery depends on migration status.",
            "reply_to_message_id": 1,
        },
    )

    exchange = rebuild_support_exchanges(db, ("helper",))[0]

    assert exchange.status == "answered_by_operator"
    assert [(member.role, member.authority, member.author) for member in exchange.members] == [
        ("requester", "none", "alice"),
        ("peer_response", "peer", "bob"),
        ("operator_response", "operator", "helper"),
    ]


def test_exchange_builder_stores_unanswered_request(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "alice",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "Can anyone help?",
        },
    )

    exchange = rebuild_support_exchanges(db, ("helper",))[0]

    assert exchange.status == "unanswered"
    assert [(member.role, member.authority, member.author) for member in exchange.members] == [
        ("requester", "none", "alice")
    ]


def test_exchange_builder_recognizes_operator_display_name(db):
    chat_id = db.upsert_chat("support", "100", "Support", "supergroup")
    db.insert_message(
        chat_id,
        {
            "message_id": 1,
            "author_id": 10,
            "author_username": "alice",
            "sent_at": "2026-06-01T12:00:00Z",
            "text": "I need help.",
        },
    )
    db.insert_message(
        chat_id,
        {
            "message_id": 2,
            "author_id": 11,
            "author_username": None,
            "author_name": "Igor",
            "sent_at": "2026-06-01T12:01:00Z",
            "text": "I can help.",
            "reply_to_message_id": 1,
        },
    )

    exchange = rebuild_support_exchanges(db, ("igor",))[0]

    assert exchange.status == "answered_by_operator"
    assert exchange.members[1].role == "operator_response"
    assert exchange.members[1].authority == "operator"
