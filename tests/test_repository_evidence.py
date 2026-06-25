from __future__ import annotations

import json

from tg_support.cli import main
from tg_support.config import config_from_dict, write_config
from tg_support.repository import CheckoutState
from tg_support.support.repository_evidence import repository_evidence


class PreparedManager:
    def __init__(self, state):
        self.state = state

    def prepare(self):
        return self.state


def test_repository_evidence_returns_matching_source_references(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "api.py").write_text("def transfer_account():\n    return 'Account transfer disabled'\n")
    state = CheckoutState(
        configured=True,
        available=True,
        checkout_path=checkout,
        branch="production",
        revision="abc123",
    )

    result = repository_evidence(PreparedManager(state), "account transfer", limit=3)

    assert result["available"] is True
    assert result["evidence"][0]["path"] == "api.py"
    assert result["evidence"][0]["revision"] == "abc123"


def test_repository_evidence_preserves_stale_warning(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "api.py").write_text("passkey login is enabled\n")
    state = CheckoutState(
        configured=True,
        available=True,
        checkout_path=checkout,
        branch="production",
        revision="oldrev",
        stale=True,
        warning="refresh_failed: network unavailable",
    )

    result = repository_evidence(PreparedManager(state), "passkey login", limit=3)

    assert result["stale"] is True
    assert "refresh_failed" in result["warning"]
    assert result["evidence"]


def test_repo_evidence_command_reports_unconfigured_repository(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr("tg_support.cli.profile_dir", lambda profile: tmp_path / profile)
    config = config_from_dict({"chat": "support", "seeds": ["example.com"]}, profile_dir_override=tmp_path / "default")
    write_config(config)

    code = main(["repo-evidence", "account transfer"])
    output = json.loads(capsys.readouterr().out)

    assert code == 0
    assert output["repository_evidence"]["configured"] is False
    assert output["repository_evidence"]["available"] is False
