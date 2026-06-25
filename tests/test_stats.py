from __future__ import annotations

from tg_support.support.stats import active_users, link_usage, message_count, replied_to_users
from tests.conftest import seed_messages


def test_message_count_since_filters_by_timestamp(db):
    seed_messages(db)
    assert message_count(db, "2026-06-02") == 1


def test_active_users_has_stable_tie_order(db):
    seed_messages(db)
    users = active_users(db)
    assert [user["user"] for user in users] == ["alice", "bob", "helper"]


def test_replied_to_users_uses_reply_metadata(db):
    seed_messages(db)
    assert replied_to_users(db) == [{"user": "alice", "replies": 1}]


def test_link_usage_counts_messages_and_resources(db):
    seed_messages(db)
    db.upsert_page("https://example.com/reset", "Reset", "Reset docs")
    links = link_usage(db)
    assert {"link": "https://example.com/reset", "count": 1} in links
    assert {"link": "resource:https://example.com/reset", "count": 1} in links
