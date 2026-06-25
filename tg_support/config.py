from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


DEFAULT_PROFILE = "default"
DEFAULT_EMBEDDING_MODEL = "local-hash-v1"
DEFAULT_BASE_DIR = Path(os.environ.get("TG_SUPPORT_HOME", Path.home() / ".tg-support"))


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class SeedConfig:
    url: str
    render: str = "auto"
    scope: str | None = None


@dataclass(frozen=True)
class SupportConfig:
    chat: str
    seeds: tuple[SeedConfig, ...]
    profile: str = DEFAULT_PROFILE
    history_limit: int = 1000
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    vector_mode: str = "fallback"
    profile_dir: Path = field(default_factory=lambda: profile_dir(DEFAULT_PROFILE))

    @property
    def db_path(self) -> Path:
        return self.profile_dir / "support.sqlite3"

    @property
    def session_path(self) -> Path:
        return self.profile_dir / "telegram.session"

    @property
    def credentials_path(self) -> Path:
        return self.profile_dir / "telegram_credentials.json"

    @property
    def authorization_path(self) -> Path:
        return self.profile_dir / "telegram_authorized.json"


@dataclass(frozen=True)
class TelegramCredentials:
    api_id: int
    api_hash: str


def normalize_chat_identifier(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ConfigError("Telegram chat identifier is required.")
    raw = re.sub(r"^https?://", "", raw)
    raw = raw.removeprefix("www.")
    raw = raw.removeprefix("t.me/")
    raw = raw.removeprefix("@")
    raw = raw.strip("/")
    if not raw:
        raise ConfigError("Telegram chat identifier is empty after normalization.")
    return raw


def canonicalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{value.strip()}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"Invalid seed URL: {value}")
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", ""))


def profile_dir(profile: str = DEFAULT_PROFILE, base_dir: Path | None = None) -> Path:
    base = base_dir or DEFAULT_BASE_DIR
    safe_profile = re.sub(r"[^A-Za-z0-9_.-]+", "-", profile).strip("-") or DEFAULT_PROFILE
    return base / "profiles" / safe_profile


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def load_config(path: Path) -> SupportConfig:
    data = json.loads(path.read_text())
    return config_from_dict(data, profile_dir_override=path.parent)


def config_from_dict(data: dict[str, Any], profile_dir_override: Path | None = None) -> SupportConfig:
    chat = normalize_chat_identifier(str(data.get("chat", "")))
    seeds_data = data.get("seeds") or []
    if not seeds_data:
        raise ConfigError("At least one website/blog seed URL is required.")
    seeds: list[SeedConfig] = []
    for item in seeds_data:
        if isinstance(item, str):
            item = {"url": item}
        render = item.get("render", "auto")
        if render not in {"auto", "always", "never"}:
            raise ConfigError("Seed render mode must be auto, always, or never.")
        seeds.append(SeedConfig(canonicalize_url(item["url"]), render=render, scope=item.get("scope")))
    profile = str(data.get("profile", DEFAULT_PROFILE))
    pdir = profile_dir_override or profile_dir(profile)
    return SupportConfig(
        chat=chat,
        seeds=tuple(seeds),
        profile=profile,
        history_limit=int(data.get("history_limit", 1000)),
        embedding_model=str(data.get("embedding_model", DEFAULT_EMBEDDING_MODEL)),
        vector_mode=str(data.get("vector_mode", "fallback")),
        profile_dir=pdir,
    )


def write_config(config: SupportConfig) -> Path:
    ensure_private_directory(config.profile_dir)
    path = config.profile_dir / "config.json"
    payload = {
        "profile": config.profile,
        "chat": config.chat,
        "history_limit": config.history_limit,
        "embedding_model": config.embedding_model,
        "vector_mode": config.vector_mode,
        "seeds": [seed.__dict__ for seed in config.seeds],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def credentials_from_dict(data: dict[str, Any]) -> TelegramCredentials:
    try:
        api_id = int(data.get("api_id", ""))
    except (TypeError, ValueError) as exc:
        raise ConfigError("Telegram API ID must be an integer.") from exc
    raw_api_hash = data.get("api_hash", "")
    if raw_api_hash is None:
        raw_api_hash = ""
    api_hash = str(raw_api_hash).strip()
    if api_id <= 0:
        raise ConfigError("Telegram API ID must be a positive integer.")
    if not api_hash:
        raise ConfigError("Telegram API hash is required.")
    return TelegramCredentials(api_id=api_id, api_hash=api_hash)


def load_telegram_credentials(path: Path) -> TelegramCredentials:
    return credentials_from_dict(json.loads(path.read_text()))


def write_telegram_credentials(config: SupportConfig, credentials: TelegramCredentials) -> Path:
    ensure_private_directory(config.profile_dir)
    path = config.credentials_path
    payload = json.dumps({"api_id": credentials.api_id, "api_hash": credentials.api_hash}, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(payload)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def write_telegram_authorization(config: SupportConfig) -> Path:
    ensure_private_directory(config.profile_dir)
    path = config.authorization_path
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(json.dumps({"authorized": True}, indent=2, sort_keys=True) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def clear_telegram_authorization(config: SupportConfig) -> None:
    try:
        config.authorization_path.unlink()
    except FileNotFoundError:
        pass
