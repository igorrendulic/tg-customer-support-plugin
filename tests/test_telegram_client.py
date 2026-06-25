from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tg_support.telegram_client import ResolvedChat, TelegramService, TelethonGateway


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


class FakeEntity:
    id = 123
    title = "Mailio"


class FakeSender:
    username = "alice"
    first_name = "Alice"


class FakeMessage:
    id = 10
    sender_id = 20
    sender = FakeSender()
    date = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    raw_text = "Hello"
    reply_to_msg_id = None


class FakeSentMessage:
    id = 99


class FakeTelethonClient:
    def __init__(self, session, _api_id, _api_hash):
        self.session = Path(session)
        self.sent = []

    def __enter__(self):
        self.session.write_text("fake session")
        self.session.chmod(0o644)
        return self

    def __exit__(self, *_args):
        return None

    def start(self):
        return self

    def is_user_authorized(self):
        return True

    def get_entity(self, chat):
        assert chat == "mailioio"
        return FakeEntity()

    def iter_messages(self, chat, limit):
        assert chat == "mailioio"
        return [FakeMessage()][:limit]

    def send_message(self, chat, text, reply_to):
        self.sent.append((chat, text, reply_to))
        return FakeSentMessage()


def test_telethon_gateway_uses_client_factory_for_login_and_resolution(tmp_path):
    gateway = TelethonGateway(tmp_path / "telegram.session", 123, "hash", client_factory=FakeTelethonClient)
    assert gateway.login() is True
    assert gateway.resolve_chat("t.me/mailioio") == ResolvedChat("mailioio", "123", "Mailio", "fakeentity")
    assert (tmp_path / "telegram.session").stat().st_mode & 0o077 == 0
    assert tmp_path.stat().st_mode & 0o077 == 0


def test_telethon_gateway_maps_history_and_reply(tmp_path):
    gateway = TelethonGateway(tmp_path / "telegram.session", 123, "hash", client_factory=FakeTelethonClient)
    assert gateway.iter_history(ResolvedChat("mailioio", "123", "Mailio", "channel"), 10) == [
        {
            "message_id": 10,
            "author_id": 20,
            "author_username": "alice",
            "author_name": "Alice",
            "sent_at": "2026-06-01T12:00:00+00:00",
            "text": "Hello",
            "reply_to_message_id": None,
        }
    ]
    assert gateway.send_reply("mailioio", "Thanks", 10) == {"message_id": 99}
