from __future__ import annotations

from tg_support.config import config_from_dict
from tg_support.repository import CommandResult, GitRunner, RepositoryManager


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
            CommandResult(0, "", ""),
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
            CommandResult(0, "", ""),
            CommandResult(0, "remoterev\trefs/heads/production", ""),
            CommandResult(1, "", "network unavailable"),
        ]
    )

    state = manager.prepare()

    assert state.available is True
    assert state.stale is True
    assert "network unavailable" in (state.warning or "")


def test_stale_checkout_successful_refresh_reports_fresh_state(tmp_path):
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
            CommandResult(0, "", ""),
            CommandResult(0, "remoterev\trefs/heads/production", ""),
            CommandResult(0, "", ""),
            CommandResult(0, "", ""),
            CommandResult(0, "production", ""),
            CommandResult(0, "remoterev", ""),
            CommandResult(0, "", ""),
        ]
    )

    state = manager.prepare()

    assert state.available is True
    assert state.stale is False
    assert state.revision == "remoterev"
    assert manager.runner.calls[4] == ["git", "-C", str(checkout), "fetch", "origin", "production"]
    assert manager.runner.calls[5] == ["git", "-C", str(checkout), "checkout", "-B", "production", "origin/production"]


def test_dirty_checkout_reports_stale_warning(tmp_path):
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
            CommandResult(0, "remoterev", ""),
            CommandResult(0, " M api.py", ""),
            CommandResult(0, "remoterev\trefs/heads/production", ""),
        ]
    )

    state = manager.prepare()

    assert state.available is True
    assert state.stale is True
    assert "dirty_checkout" in (state.warning or "")


def test_branch_change_fetches_before_checkout(tmp_path):
    checkout = tmp_path / "profile" / "repositories" / "repo"
    (checkout / ".git").mkdir(parents=True)
    config = config_from_dict(
        {"chat": "support", "seeds": ["example.com"], "repository": {"repository": "owner/project", "branch": "main"}},
        profile_dir_override=tmp_path / "profile",
    )
    manager = RepositoryManager(config, runner=FakeRunner([]))
    manager.checkout_dir = lambda _repo=None: checkout  # type: ignore[method-assign]
    manager.runner = FakeRunner(
        [
            CommandResult(0, "production", ""),
            CommandResult(1, "", "pathspec 'main' did not match"),
            CommandResult(0, "", ""),
            CommandResult(0, "", ""),
            CommandResult(0, "main", ""),
            CommandResult(0, "mainrev", ""),
            CommandResult(0, "", ""),
            CommandResult(0, "mainrev\trefs/heads/main", ""),
        ]
    )

    state = manager.prepare()

    assert state.available is True
    assert state.branch == "main"
    assert state.revision == "mainrev"
    assert manager.runner.calls[2] == ["git", "-C", str(checkout), "fetch", "origin", "main"]
    assert manager.runner.calls[3] == ["git", "-C", str(checkout), "checkout", "-B", "main", "origin/main"]


def test_missing_git_reports_command_result(monkeypatch):
    def raise_missing_git(*_args, **_kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr("subprocess.run", raise_missing_git)

    result = GitRunner().run(["git", "status"])

    assert result.returncode == 1
    assert "git not found" in result.stderr


def test_checkout_parent_creation_failure_reports_unavailable(tmp_path, monkeypatch):
    config = config_from_dict(
        {"chat": "support", "seeds": ["example.com"], "repository": {"repository": "owner/project", "branch": "production"}},
        profile_dir_override=tmp_path / "profile",
    )

    def raise_permission(_path):
        raise PermissionError("permission denied")

    monkeypatch.setattr("tg_support.repository.ensure_private_directory", raise_permission)

    state = RepositoryManager(config, runner=FakeRunner([])).prepare()

    assert state.available is False
    assert "permission denied" in (state.error or "")


def test_missing_repository_config_reports_unavailable(tmp_path):
    config = config_from_dict({"chat": "support", "seeds": ["example.com"]}, profile_dir_override=tmp_path / "profile")

    state = RepositoryManager(config).prepare()

    assert state.configured is False
    assert state.available is False
