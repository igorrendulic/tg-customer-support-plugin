from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import sqlite3

from tg_support.cli import main
from tg_support.config import load_config, write_telegram_authorization
from tg_support.indexing.chunking import chunk_messages
from tg_support.indexing.embeddings import RetrievalDependencyError
from tg_support.storage.db import SupportDatabase
from tg_support.support.drafting import create_draft
from tg_support.support.context import draft_context
from tg_support.telegram_client import TelegramError
from tests.conftest import make_test_retriever, patch_test_retriever, seed_messages


def test_cli_setup_stores_normalized_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(["--profile", "demo", "setup", "--chat", "@support", "--seed", "example.com/blog"])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    config = load_config(tmp_path / "demo" / "config.json")
    assert config.chat == "support"
    assert config.embedding_model == "BAAI/bge-small-en-v1.5"
    assert config.vector_mode == "sqlite-vec"


def test_cli_setup_stores_optional_repository_config(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    code = main(
        [
            "--profile",
            "demo",
            "setup",
            "--chat",
            "@support",
            "--seed",
            "example.com/blog",
            "--repository",
            "owner/project",
            "--repository-branch",
            "production",
        ]
    )
    assert code == 0
    capsys.readouterr()
    config = load_config(tmp_path / "demo" / "config.json")
    assert config.repository is not None
    assert config.repository.repository == "https://github.com/owner/project.git"
    assert config.repository.branch == "production"


def test_status_reports_repository_config_without_blocking_readiness(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert (
        main(
            [
                "setup",
                "--chat",
                "support",
                "--seed",
                "example.com/blog",
                "--repository",
                "owner/project",
                "--repository-branch",
                "production",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["status"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["features"]["repository_evidence"] is True
    assert output["repository"] == {"repository": "https://github.com/owner/project.git", "branch": "production"}
    assert output["next_action"] == "credentials"


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
    patch_test_retriever(monkeypatch)
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


def test_index_reports_retrieval_dependency_errors(tmp_path, capsys, monkeypatch):
    class FailingRetriever:
        def __init__(self, _db, *args, **kwargs):
            pass

        def build(self, *args, **kwargs):
            raise RetrievalDependencyError("missing vector support")

    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    monkeypatch.setattr("tg_support.cli.HybridRetriever", FailingRetriever)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()

    code = main(["index"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"] == "missing vector support"
    assert output["next_action"] == "install retrieval dependencies and rerun index"
    assert output["sqlite_version"] == sqlite3.sqlite_version


def test_search_before_index_reports_next_action(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    capsys.readouterr()

    code = main(["search", "password reset"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output == {"ok": False, "error": "Search index has not been built.", "next_action": "index"}


def test_search_reports_retrieval_dependency_errors(tmp_path, capsys, monkeypatch):
    class FailingRetriever:
        def __init__(self, _db, *args, **kwargs):
            pass

        def search_with_conflicts(self, *_args, **_kwargs):
            raise RetrievalDependencyError("sqlite extension unavailable")

    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    monkeypatch.setattr("tg_support.cli.HybridRetriever", FailingRetriever)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    db = SupportDatabase(config.db_path)
    db.upsert_chunk("web", 1, 0, "indexed text")
    db.rebuild_documents()
    capsys.readouterr()

    code = main(["search", "indexed"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"] == "sqlite extension unavailable"
    assert output["sqlite_version"] == sqlite3.sqlite_version


def test_draft_context_reports_retrieval_dependency_errors(tmp_path, capsys, monkeypatch):
    class FailingRetriever:
        def __init__(self, _db, *args, **kwargs):
            pass

        def search_with_conflicts(self, *_args, **_kwargs):
            raise RetrievalDependencyError("sqlite extension unavailable")

    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    monkeypatch.setattr("tg_support.cli.HybridRetriever", FailingRetriever)
    assert main(["setup", "--chat", "support", "--seed", "example.com/blog"]) == 0
    config = load_config(tmp_path / "default" / "config.json")
    db = SupportDatabase(config.db_path)
    db.upsert_chunk("web", 1, 0, "indexed text")
    db.rebuild_documents()
    capsys.readouterr()

    code = main(["draft-context", "--query", "indexed"])
    output = json.loads(capsys.readouterr().out)

    assert code == 2
    assert output["ok"] is False
    assert output["error"] == "sqlite extension unavailable"
    assert output["sqlite_version"] == sqlite3.sqlite_version


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


def test_draft_context_for_known_user(db, monkeypatch):
    patch_test_retriever(monkeypatch)
    seed_messages(db)
    chunk_messages(db)
    make_test_retriever(db).build()
    context = draft_context(db, "password reset", username="alice")
    assert context["history"]
    assert context["target"]["username"] == "alice"


def test_skill_documents_status_preflight():
    skill = Path("skills/telegram-support/SKILL.md").read_text()
    assert "status" in skill
    assert "next_action" in skill
    assert "credentials --api-id <id> --api-hash-stdin" in skill
    assert "knowledge-add" in skill
    assert "conflicts" in skill


def test_openai_agent_exposes_setup_commands():
    agent = Path("agents/openai.yaml").read_text()
    assert "status:" in agent
    assert "credentials:" in agent
    assert "login:" in agent
    assert "knowledge_add:" in agent
    assert "repo_evidence:" in agent
    assert "product-behavior" in agent
    assert "stale checkout warnings" in agent


def test_reply_workflow_requires_conflict_resolution():
    workflow = Path("skills/telegram-support/references/reply-workflow.md").read_text()
    assert "conflicts" in workflow
    assert "Manual Knowledge Note" in workflow
    assert "repo-evidence" in workflow
    assert "Repository Evidence" in workflow


def test_operator_docs_describe_manual_knowledge():
    readme = Path("README.md").read_text()
    setup = Path("docs/setup.md").read_text()
    assert "knowledge-add" in readme
    assert "Manual Knowledge Notes" in setup
    assert "conflicts" in setup


def test_operator_docs_describe_optional_repository_evidence():
    readme = Path("README.md").read_text()
    setup = Path("docs/setup.md").read_text()
    skill = Path("skills/telegram-support/SKILL.md").read_text()
    claude_usage = Path("docs/claude-usage.md").read_text()
    assert "repo-evidence" in readme
    assert "--repository owner/project" in setup
    assert "stale" in setup
    assert "Repository Evidence" in skill
    assert "skip repository setup" in skill
    assert "--repository <owner/repo-or-url-or-path>" in skill
    assert "repo-evidence" in claude_usage
    assert "product-behavior" in claude_usage
