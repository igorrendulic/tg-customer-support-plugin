from __future__ import annotations

from pathlib import Path

import pytest

from tg_support.config import (
    DEFAULT_BASE_DIR,
    DEFAULT_EMBEDDING_MODEL,
    ConfigError,
    canonicalize_url,
    canonicalize_repository,
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


def test_setup_config_allows_no_seed(tmp_path):
    config = config_from_dict({"chat": "support", "seeds": []}, profile_dir_override=tmp_path)
    assert config.seeds == ()


def test_config_stores_profile_outside_source_tree(tmp_path):
    config = config_from_dict(
        {"chat": "@support", "seeds": ["example.com/blog"], "history_limit": 20},
        profile_dir_override=tmp_path / "profile",
    )
    assert config.chat == "support"
    assert config.seeds[0].url == "https://example.com/blog"
    assert config.profile_dir == tmp_path / "profile"
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.vector_mode == "sqlite-vec"


def test_config_preserves_retrieval_defaults(tmp_path):
    config = config_from_dict(
        {"chat": "@support", "seeds": ["example.com/blog"], "embedding_model": DEFAULT_EMBEDDING_MODEL, "vector_mode": "sqlite-vec"},
        profile_dir_override=tmp_path / "profile",
    )
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.vector_mode == "sqlite-vec"


def test_config_normalizes_operator_identities(tmp_path):
    config = config_from_dict(
        {
            "chat": "@support",
            "operator_identities": ["@IgorMailio", " igormailio ", "Igor"],
        },
        profile_dir_override=tmp_path / "profile",
    )

    assert config.operator_identities == ("igormailio", "igor")


def test_config_allows_missing_operator_identities(tmp_path):
    config = config_from_dict({"chat": "@support"}, profile_dir_override=tmp_path / "profile")

    assert config.operator_identities == ()


def test_config_rejects_blank_operator_identity(tmp_path):
    with pytest.raises(ConfigError, match="Operator identity cannot be blank"):
        config_from_dict(
            {"chat": "@support", "operator_identities": ["igormailio", "   "]},
            profile_dir_override=tmp_path / "profile",
        )


def test_config_rejects_unsupported_embedding_model(tmp_path):
    with pytest.raises(ConfigError, match="Unsupported embedding model"):
        config_from_dict(
            {"chat": "@support", "seeds": ["example.com/blog"], "embedding_model": "custom-model"},
            profile_dir_override=tmp_path / "profile",
        )


def test_config_rejects_unsupported_vector_mode(tmp_path):
    with pytest.raises(ConfigError, match="Unsupported vector mode"):
        config_from_dict(
            {"chat": "@support", "seeds": ["example.com/blog"], "vector_mode": "custom-vector"},
            profile_dir_override=tmp_path / "profile",
        )


def test_default_profile_dir_uses_dot_tg_support_home():
    assert DEFAULT_BASE_DIR == Path.home() / ".tg-support"
    assert profile_dir("demo") == Path.home() / ".tg-support" / "profiles" / "demo"


def test_canonical_url_removes_fragment_and_trailing_slash():
    assert canonicalize_url("https://Example.com/blog/#top") == "https://example.com/blog"


def test_repository_config_round_trips_owner_repo(tmp_path):
    config = config_from_dict(
        {"chat": "@support", "seeds": ["example.com/blog"], "repository": {"repository": "owner/project", "branch": "production"}},
        profile_dir_override=tmp_path / "profile",
    )
    assert config.repository is not None
    assert config.repository.repository == "https://github.com/owner/project.git"
    assert config.repository.branch == "production"


def test_repository_config_accepts_git_ssh_shorthand(tmp_path):
    config = config_from_dict(
        {
            "chat": "@support",
            "seeds": ["example.com/blog"],
            "repository": {"repository": "git@github.com:owner/project.git", "branch": "production"},
        },
        profile_dir_override=tmp_path / "profile",
    )
    assert config.repository is not None
    assert config.repository.repository == "git@github.com:owner/project.git"


def test_repository_config_is_optional(tmp_path):
    config = config_from_dict({"chat": "@support", "seeds": ["example.com/blog"]}, profile_dir_override=tmp_path / "profile")
    assert config.repository is None


def test_repository_branch_defaults_to_main(tmp_path):
    config = config_from_dict(
        {"chat": "@support", "repository": {"repository": "owner/project"}},
        profile_dir_override=tmp_path / "profile",
    )
    assert config.repository is not None
    assert config.repository.branch == "main"


def test_repository_config_rejects_invalid_values():
    with pytest.raises(ConfigError):
        canonicalize_repository("not a repo")
    with pytest.raises(ConfigError):
        config_from_dict(
            {"chat": "@support", "seeds": ["example.com/blog"], "repository": {"repository": "owner/project", "branch": "../main"}}
        )


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
