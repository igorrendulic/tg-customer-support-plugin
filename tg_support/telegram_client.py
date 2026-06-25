from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from tg_support.config import normalize_chat_identifier
from tg_support.storage.db import SupportDatabase


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
    def __init__(self, session_path, api_id: str | None = None, api_hash: str | None = None):
        self.session_path = session_path
        self.api_id = api_id
        self.api_hash = api_hash

    def _unsupported(self):
        raise TelegramError(
            "Real Telegram access requires installing the telegram extra and configuring Telethon API credentials."
        )

    def login(self) -> bool:
        self._unsupported()

    def resolve_chat(self, chat: str) -> ResolvedChat:
        self._unsupported()

    def iter_history(self, chat: ResolvedChat, limit: int) -> list[dict[str, Any]]:
        self._unsupported()

    def send_reply(self, chat: str, text: str, reply_to_message_id: int) -> dict[str, Any]:
        self._unsupported()


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
