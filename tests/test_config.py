from __future__ import annotations

from pathlib import Path

import pytest

from tg_support.config import (
    DEFAULT_BASE_DIR,
    ConfigError,
    canonicalize_url,
    config_from_dict,
    credentials_from_dict,
    load_telegram_credentials,
    normalize_chat_identifier,
    profile_dir,
    write_telegram_credentials,
)


@pytest.mark.parametrize("value", ["channel-name", "@channel-name", "https://t.me/channel-name", "t.me/channel-name/"])
def test_chat_identifier_normalizes(value):
    assert normalize_chat_identifier(value) == "channel-name"


def test_setup_config_requires_seed(tmp_path):
    with pytest.raises(ConfigError):
        config_from_dict({"chat": "support", "seeds": []}, profile_dir_override=tmp_path)


def test_config_stores_profile_outside_source_tree(tmp_path):
    config = config_from_dict(
        {"chat": "@support", "seeds": ["example.com/blog"], "history_limit": 20},
        profile_dir_override=tmp_path / "profile",
    )
    assert config.chat == "support"
    assert config.seeds[0].url == "https://example.com/blog"
    assert config.profile_dir == tmp_path / "profile"


def test_default_profile_dir_uses_dot_tg_support_home():
    assert DEFAULT_BASE_DIR == Path.home() / ".tg-support"
    assert profile_dir("demo") == Path.home() / ".tg-support" / "profiles" / "demo"


def test_canonical_url_removes_fragment_and_trailing_slash():
    assert canonicalize_url("https://Example.com/blog/#top") == "https://example.com/blog"


def test_telegram_credentials_validate():
    credentials = credentials_from_dict({"api_id": "123", "api_hash": "hash"})
    assert credentials.api_id == 123
    assert credentials.api_hash == "hash"


def test_telegram_credentials_require_valid_values():
    with pytest.raises(ConfigError):
        credentials_from_dict({"api_id": "not-a-number", "api_hash": "hash"})
    with pytest.raises(ConfigError):
        credentials_from_dict({"api_id": "123", "api_hash": ""})
    with pytest.raises(ConfigError):
        credentials_from_dict({"api_id": "123", "api_hash": None})


def test_telegram_credentials_store_profile_local_with_owner_permissions(tmp_path):
    config = config_from_dict({"chat": "@support", "seeds": ["example.com/blog"]}, profile_dir_override=tmp_path / "profile")
    path = write_telegram_credentials(config, credentials_from_dict({"api_id": "123", "api_hash": "secret"}))
    assert path == tmp_path / "profile" / "telegram_credentials.json"
    assert load_telegram_credentials(path).api_hash == "secret"
    assert path.stat().st_mode & 0o077 == 0
    assert config.profile_dir.stat().st_mode & 0o077 == 0


def test_telegram_credentials_rewrite_fixes_existing_permissions(tmp_path):
    config = config_from_dict({"chat": "@support", "seeds": ["example.com/blog"]}, profile_dir_override=tmp_path / "profile")
    config.profile_dir.mkdir(parents=True)
    path = config.credentials_path
    path.write_text("old")
    path.chmod(0o644)

    write_telegram_credentials(config, credentials_from_dict({"api_id": "123", "api_hash": "secret"}))

    assert load_telegram_credentials(path).api_hash == "secret"
    assert path.stat().st_mode & 0o077 == 0
