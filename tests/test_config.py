from __future__ import annotations

from pathlib import Path

import pytest

from tg_support.config import DEFAULT_BASE_DIR, ConfigError, canonicalize_url, config_from_dict, normalize_chat_identifier, profile_dir


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
