from __future__ import annotations

from tg_support.telegram_client import ResolvedChat, TelegramService


class FakeGateway:
    def __init__(self, fail_login=False):
        self.fail_login = fail_login

    def login(self):
        return not self.fail_login

    def resolve_chat(self, chat):
        return ResolvedChat(chat, "100", "Support", "supergroup")

    def iter_history(self, chat, limit):
        return [
            {
                "message_id": 1,
                "author_id": 10,
                "author_username": "alice",
                "sent_at": "2026-06-01T12:00:00Z",
                "text": "Help with billing",
                "reply_to_message_id": None,
            }
        ][:limit]

    def send_reply(self, chat, text, reply_to_message_id):
        return {"message_id": 99}


def test_history_ingestion_uses_fake_gateway(db):
    service = TelegramService(db, FakeGateway())
    assert service.ingest_history("@support", 100) == 1
    assert db.count("messages") == 1


def test_login_cancellation_does_not_mark_session(db):
    service = TelegramService(db, FakeGateway(fail_login=True))
    assert service.login() is False
    assert db.count("chats") == 0
