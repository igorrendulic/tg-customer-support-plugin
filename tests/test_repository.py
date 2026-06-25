from __future__ import annotations

from pathlib import Path

from tg_support.config import config_from_dict
from tg_support.repository import CommandResult, RepositoryManager


class FakeRunner:
    def __init__(self, results: list[CommandResult]):
        self.results = list(results)
        self.calls: list[list[str]] = []

    def run(self, args, cwd=None):
        self.calls.append(args)
        return self.results.pop(0)


def test_checkout_created_under_profile(tmp_path):
    config = config_from_dict(
        {"chat": "support", "seeds": ["example.com"], "repository": {"repository": "owner/project", "branch": "production"}},
        profile_dir_override=tmp_path / "profile",
    )
    runner = FakeRunner(
        [
            CommandResult(0, "", ""),
            CommandResult(0, "production", ""),
            CommandResult(0, "abc123", ""),
        ]
    )

    state = RepositoryManager(config, runner=runner).prepare()

    assert state.available is True
    assert state.checkout_path == tmp_path / "profile" / "repositories" / state.checkout_path.name
    assert runner.calls[0][:4] == ["git", "clone", "--branch", "production"]


def test_stale_checkout_refresh_failure_keeps_checkout_available(tmp_path):
    checkout = tmp_path / "profile" / "repositories" / "repo"
    (checkout / ".git").mkdir(parents=True)
    config = config_from_dict(
        {"chat": "support", "seeds": ["example.com"], "repository": {"repository": "owner/project", "branch": "production"}},
        profile_dir_override=tmp_path / "profile",
    )
    manager = RepositoryManager(config, runner=FakeRunner([]))
    manager.checkout_dir = lambda _repo=None: checkout  # type: ignore[method-assign]
    manager.runner = FakeRunner(
        [
            CommandResult(0, "production", ""),
            CommandResult(0, "localrev", ""),
            CommandResult(0, "remoterev\trefs/heads/production", ""),
            CommandResult(1, "", "network unavailable"),
        ]
    )

    state = manager.prepare()

    assert state.available is True
    assert state.stale is True
    assert "network unavailable" in (state.warning or "")


def test_missing_repository_config_reports_unavailable(tmp_path):
    config = config_from_dict({"chat": "support", "seeds": ["example.com"]}, profile_dir_override=tmp_path / "profile")

    state = RepositoryManager(config).prepare()

    assert state.configured is False
    assert state.available is False
