from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

from tg_support.cli import main
from tg_support.config import load_config, write_telegram_authorization
from tg_support.storage.db import SupportDatabase
from tg_support.support.drafting import create_draft
from tg_support.support.context import draft_context
from tg_support.telegram_client import TelegramError
from tests.conftest import seed_messages


def test_cli_setup_stores_normalized_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(["--profile", "demo", "setup", "--chat", "@support", "--seed", "example.com/blog"])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    config = load_config(tmp_path / "demo" / "config.json")
    assert config.chat == "support"


def test_missing_setup_inputs_fail_without_profile(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(["setup", "--chat", "support"])
    assert code == 2
    assert not (tmp_path / "default" / "config.json").exists()


def test_status_without_profile_suggests_setup(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(["status"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["ok"] is False
    assert output["checks"]["config"] is False
    assert output["next_action"] == "setup"


def test_status_after_setup_suggests_credentials(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "t.me/mailioio", "--seed", "https://mailio.io/blog"]) == 0
    capsys.readouterr()
    code = main(["status"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["ok"] is False
    assert output["chat"] == "mailioio"
    assert output["checks"]["credentials"] is False
    assert output["next_action"] == "credentials"


def test_credentials_command_redacts_secret(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", StringIO("secret\n"))
    code = main(["credentials", "--api-id", "123", "--api-hash-stdin"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0
    assert output["api_id"] == 123
    assert output["api_hash"] == "<redacted>"
    assert "secret" not in json.dumps(output)


def test_login_without_credentials_returns_actionable_error(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()
    code = main(["login"])
    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output["ok"] is False
    assert "credentials" in output["error"]


def test_credentials_without_stdin_or_tty_fails_actionably(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()
    code = main(["credentials", "--api-id", "123"])
    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output["ok"] is False
    assert "--api-hash-stdin" in output["error"]


def test_status_progresses_through_corpus_readiness(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    monkeypatch.setattr("sys.stdin", StringIO("secret\n"))
    assert main(["credentials", "--api-id", "123", "--api-hash-stdin"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    config.session_path.write_text("fake session")
    write_telegram_authorization(config)
    capsys.readouterr()

    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["next_action"] == "sync"

    db = SupportDatabase(config.db_path)
    seed_messages(db)
    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["next_action"] == "crawl"

    db.upsert_page("https://example.com/blog", "Blog", "Useful support article")
    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["next_action"] == "index"

    assert main(["index"]) == 0
    capsys.readouterr()
    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["next_action"] == "ready"


def test_status_with_session_file_but_no_authorization_still_suggests_login(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    monkeypatch.setattr("sys.stdin", StringIO("secret\n"))
    assert main(["credentials", "--api-id", "123", "--api-hash-stdin"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    config.session_path.write_text("partial session")
    capsys.readouterr()

    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["checks"]["telegram_session"] is False
    assert output["next_action"] == "login"


def test_status_reports_missing_database_schema_as_setup(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    config.db_path.unlink()
    capsys.readouterr()

    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["checks"]["database"] is False
    assert output["next_action"] == "setup"


def test_status_ignores_failed_crawl_for_readiness(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    monkeypatch.setattr("sys.stdin", StringIO("secret\n"))
    assert main(["credentials", "--api-id", "123", "--api-hash-stdin"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    config.session_path.write_text("fake session")
    write_telegram_authorization(config)
    db = SupportDatabase(config.db_path)
    seed_messages(db)
    db.upsert_page("https://example.com/blog", None, "", status="error", error="boom")
    capsys.readouterr()

    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["next_action"] == "crawl"


def test_confirm_telegram_error_returns_json_and_keeps_token_retryable(tmp_path, capsys, monkeypatch):
    class FailingGateway:
        def __init__(self, *_args):
            pass

        def send_reply(self, *_args):
            raise TelegramError("telegram unavailable")

    class SuccessGateway:
        def __init__(self, *_args):
            pass

        def send_reply(self, *_args):
            return {"message_id": 777}

    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    monkeypatch.setattr("sys.stdin", StringIO("secret\n"))
    assert main(["credentials", "--api-id", "123", "--api-hash-stdin"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    draft = create_draft(SupportDatabase(config.db_path), "support", "hello", {}, target_message_id=10)
    capsys.readouterr()

    monkeypatch.setattr("tg_support.cli.TelethonGateway", FailingGateway)
    code = main(["confirm", draft["post_token"]])
    output = json.loads(capsys.readouterr().out)
    assert code == 2
    assert output == {"ok": False, "error": "telegram unavailable"}

    monkeypatch.setattr("tg_support.cli.TelethonGateway", SuccessGateway)
    assert main(["confirm", draft["post_token"]]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert output["telegram_message_id"] == 777


def test_draft_context_for_known_user(db):
    seed_messages(db)
    context = draft_context(db, "password reset", username="alice")
    assert context["history"]
    assert context["target"]["username"] == "alice"


def test_skill_documents_status_preflight():
    skill = Path("skills/telegram-support/SKILL.md").read_text()
    assert "status" in skill
    assert "next_action" in skill
    assert "credentials --api-id <id> --api-hash-stdin" in skill


def test_openai_agent_exposes_setup_commands():
    agent = Path("agents/openai.yaml").read_text()
    assert "status:" in agent
    assert "credentials:" in agent
    assert "login:" in agent
