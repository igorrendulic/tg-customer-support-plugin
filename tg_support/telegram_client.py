from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, Protocol

from tg_support.config import ensure_private_directory, normalize_chat_identifier
from tg_support.storage.db import SupportDatabase

MISSING_CREDENTIALS_ERROR = "Telegram API credentials are missing or invalid. Run the credentials command for this profile."


class TelegramError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedChat:
    input: str
    telegram_id: str
    title: str
    type: str


class TelegramGateway(Protocol):
    def login(self) -> bool: ...
    def resolve_chat(self, chat: str) -> ResolvedChat: ...
    def iter_history(self, chat: ResolvedChat, limit: int) -> list[dict[str, Any]]: ...
    def send_reply(self, chat: str, text: str, reply_to_message_id: int) -> dict[str, Any]: ...


class TelethonGateway:
    def __init__(self, session_path, api_id: int | None = None, api_hash: str | None = None, client_factory=None):
        self.session_path = Path(session_path)
        self.api_id = api_id
        self.api_hash = api_hash
        self.client_factory = client_factory

    def _client(self):
        if not self.api_id or not self.api_hash:
            raise TelegramError(MISSING_CREDENTIALS_ERROR)
        ensure_private_directory(self.session_path.parent)
        if self.client_factory is not None:
            return self.client_factory(str(self.session_path), self.api_id, self.api_hash)
        try:
            from telethon.sync import TelegramClient
        except ImportError as exc:
            raise TelegramError("Real Telegram access requires installing the telegram extra.") from exc
        return TelegramClient(str(self.session_path), self.api_id, self.api_hash)

    def _run(self, action):
        try:
            with self._client() as client:
                return action(client)
        except TelegramError:
            raise
        except Exception as exc:
            raise TelegramError(str(exc)) from exc
        finally:
            self._secure_session_file()

    def _secure_session_file(self):
        try:
            if self.session_path.exists():
                self.session_path.chmod(0o600)
        except OSError:
            pass

    def login(self) -> bool:
        def action(client):
            if hasattr(client, "start"):
                client.start()
            if hasattr(client, "is_user_authorized"):
                return bool(client.is_user_authorized())
            return True

        return bool(self._run(action))

    def resolve_chat(self, chat: str) -> ResolvedChat:
        normalized = normalize_chat_identifier(chat)

        def action(client):
            entity = client.get_entity(normalized)
            title = (
                getattr(entity, "title", None)
                or getattr(entity, "username", None)
                or getattr(entity, "first_name", None)
                or normalized
            )
            type_name = entity.__class__.__name__.lower()
            return ResolvedChat(normalized, str(getattr(entity, "id", "")), str(title), type_name)

        return self._run(action)

    def iter_history(self, chat: ResolvedChat, limit: int) -> list[dict[str, Any]]:
        def action(client):
            messages = []
            for message in client.iter_messages(chat.input, limit=limit):
                sender = getattr(message, "sender", None)
                sent_at = getattr(message, "date", None)
                if sent_at is not None and getattr(sent_at, "tzinfo", None) is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
                messages.append(
                    {
                        "message_id": getattr(message, "id"),
                        "author_id": getattr(message, "sender_id", None),
                        "author_username": getattr(sender, "username", None),
                        "author_name": getattr(sender, "first_name", None) or getattr(sender, "title", None),
                        "sent_at": sent_at.isoformat() if sent_at is not None else "",
                        "text": getattr(message, "raw_text", None) or getattr(message, "message", None) or "",
                        "reply_to_message_id": getattr(message, "reply_to_msg_id", None),
                    }
                )
            return messages

        return self._run(action)

    def send_reply(self, chat: str, text: str, reply_to_message_id: int) -> dict[str, Any]:
        normalized = normalize_chat_identifier(chat)

        def action(client):
            result = client.send_message(normalized, text, reply_to=reply_to_message_id)
            return {"message_id": getattr(result, "id", None)}

        return self._run(action)


class TelegramService:
    def __init__(self, db: SupportDatabase, gateway: TelegramGateway):
        self.db = db
        self.gateway = gateway

    def login(self) -> bool:
        return self.gateway.login()

    def resolve_and_store_chat(self, chat_input: str) -> int:
        normalized = normalize_chat_identifier(chat_input)
        resolved = self.gateway.resolve_chat(normalized)
        return self.db.upsert_chat(resolved.input, resolved.telegram_id, resolved.title, resolved.type)

    def ingest_history(self, chat_input: str, limit: int) -> int:
        normalized = normalize_chat_identifier(chat_input)
        resolved = self.gateway.resolve_chat(normalized)
        chat_id = self.db.upsert_chat(resolved.input, resolved.telegram_id, resolved.title, resolved.type)
        inserted = 0
        for message in self.gateway.iter_history(resolved, limit):
            self.db.insert_message(chat_id, message)
            inserted += 1
        return inserted
