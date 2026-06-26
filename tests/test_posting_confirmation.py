from __future__ import annotations

import pytest

from tg_support.support.drafting import create_draft
from tg_support.support.posting import PostingError, apply_confirmation
from tg_support.telegram_client import TelegramError


class SendGateway:
    def __init__(self):
        self.calls = []

    def login(self):
        return True

    def resolve_chat(self, chat):
        raise NotImplementedError

    def iter_history(self, chat, limit):
        raise NotImplementedError

    def send_reply(self, chat, text, reply_to_message_id):
        self.calls.append((chat, text, reply_to_message_id))
        return {"message_id": 500}


class FailingGateway:
    def send_reply(self, *_args):
        raise TelegramError("telegram unavailable")


def test_cancelled_draft_does_not_send(db):
    gateway = SendGateway()
    draft = create_draft(db, "support", "hello", {}, target_message_id=10)
    result = apply_confirmation(db, draft["cancel_token"], gateway)
    assert result["status"] == "cancelled"
    assert gateway.calls == []


def test_confirmation_tokens_are_cli_safe(db):
    draft = create_draft(db, "support", "hello", {}, target_message_id=10)

    assert draft["post_token"].startswith("post_")
    assert draft["cancel_token"].startswith("cancel_")
    assert not draft["post_token"].startswith("-")
    assert not draft["cancel_token"].startswith("-")


def test_confirmed_draft_sends_once(db):
    gateway = SendGateway()
    draft = create_draft(db, "support", "hello", {}, target_message_id=10)
    result = apply_confirmation(db, draft["post_token"], gateway)
    assert result["status"] == "posted"
    assert gateway.calls == [("support", "hello", 10)]
    with pytest.raises(PostingError):
        apply_confirmation(db, draft["post_token"], gateway)


def test_post_without_reply_target_fails(db):
    gateway = SendGateway()
    draft = create_draft(db, "support", "hello", {}, target_message_id=None)
    with pytest.raises(PostingError):
        apply_confirmation(db, draft["post_token"], gateway)
    assert gateway.calls == []


def test_missing_gateway_does_not_consume_post_token(db):
    draft = create_draft(db, "support", "hello", {}, target_message_id=10)
    with pytest.raises(PostingError):
        apply_confirmation(db, draft["post_token"])
    gateway = SendGateway()
    result = apply_confirmation(db, draft["post_token"], gateway)
    assert result["status"] == "posted"


def test_failed_gateway_send_does_not_consume_post_token(db):
    draft = create_draft(db, "support", "hello", {}, target_message_id=10)
    with pytest.raises(TelegramError):
        apply_confirmation(db, draft["post_token"], FailingGateway())

    gateway = SendGateway()
    result = apply_confirmation(db, draft["post_token"], gateway)
    assert result["status"] == "posted"
    assert gateway.calls == [("support", "hello", 10)]
