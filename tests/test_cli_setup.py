from __future__ import annotations

import json

from tg_support.cli import main
from tg_support.config import load_config
from tg_support.support.context import draft_context
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


def test_draft_context_for_known_user(db):
    seed_messages(db)
    context = draft_context(db, "password reset", username="alice")
    assert context["history"]
    assert context["target"]["username"] == "alice"
