from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tg_support.config import RepositoryConfig, SupportConfig, ensure_private_directory


class RepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class CheckoutState:
    configured: bool
    available: bool
    checkout_path: Path | None = None
    branch: str | None = None
    revision: str | None = None
    stale: bool = False
    warning: str | None = None
    error: str | None = None


class GitRunner:
    def run(self, args: list[str], cwd: Path | None = None) -> CommandResult:
        completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
        return CommandResult(completed.returncode, completed.stdout.strip(), completed.stderr.strip())


class RepositoryManager:
    def __init__(self, config: SupportConfig, runner: GitRunner | None = None):
        self.config = config
        self.runner = runner or GitRunner()

    def checkout_dir(self, repository: RepositoryConfig | None = None) -> Path:
        repo = repository or self._require_repo()
        digest = hashlib.sha1(repo.repository.encode("utf-8")).hexdigest()[:12]
        return self.config.profile_dir / "repositories" / digest

    def prepare(self) -> CheckoutState:
        if self.config.repository is None:
            return CheckoutState(configured=False, available=False, warning="repository_not_configured")
        repo = self.config.repository
        checkout = self.checkout_dir(repo)
        ensure_private_directory(checkout.parent)
        if not (checkout / ".git").exists():
            clone = self.runner.run(["git", "clone", "--branch", repo.branch, "--single-branch", repo.repository, str(checkout)])
            if clone.returncode != 0:
                return CheckoutState(
                    configured=True,
                    available=False,
                    checkout_path=checkout,
                    branch=repo.branch,
                    error=clone.stderr or clone.stdout or "clone failed",
                )
            return self._state(checkout, repo.branch)

        state = self._state(checkout, repo.branch)
        if not state.available:
            return state
        remote_revision = self._remote_revision(repo)
        if remote_revision is None:
            return CheckoutState(
                configured=True,
                available=True,
                checkout_path=checkout,
                branch=repo.branch,
                revision=state.revision,
                stale=True,
                warning="refresh_failed: unable to check remote branch",
            )
        if state.revision == remote_revision:
            return state
        refresh = self._refresh(checkout, repo.branch)
        if refresh.returncode != 0:
            return CheckoutState(
                configured=True,
                available=True,
                checkout_path=checkout,
                branch=repo.branch,
                revision=state.revision,
                stale=True,
                warning=f"refresh_failed: {refresh.stderr or refresh.stdout or 'git refresh failed'}",
            )
        return self._state(checkout, repo.branch)

    def _require_repo(self) -> RepositoryConfig:
        if self.config.repository is None:
            raise RepositoryError("Repository is not configured.")
        return self.config.repository

    def _state(self, checkout: Path, branch: str) -> CheckoutState:
        branch_result = self.runner.run(["git", "-C", str(checkout), "rev-parse", "--abbrev-ref", "HEAD"])
        if branch_result.returncode != 0:
            return CheckoutState(configured=True, available=False, checkout_path=checkout, branch=branch, error=branch_result.stderr)
        if branch_result.stdout != branch:
            checkout_result = self.runner.run(["git", "-C", str(checkout), "checkout", branch])
            if checkout_result.returncode != 0:
                return CheckoutState(configured=True, available=False, checkout_path=checkout, branch=branch, error=checkout_result.stderr)
        revision = self.runner.run(["git", "-C", str(checkout), "rev-parse", "HEAD"])
        if revision.returncode != 0:
            return CheckoutState(configured=True, available=False, checkout_path=checkout, branch=branch, error=revision.stderr)
        return CheckoutState(configured=True, available=True, checkout_path=checkout, branch=branch, revision=revision.stdout)

    def _remote_revision(self, repo: RepositoryConfig) -> str | None:
        result = self.runner.run(["git", "ls-remote", repo.repository, f"refs/heads/{repo.branch}"])
        if result.returncode != 0 or not result.stdout:
            return None
        return result.stdout.split()[0]

    def _refresh(self, checkout: Path, branch: str) -> CommandResult:
        fetch = self.runner.run(["git", "-C", str(checkout), "fetch", "origin", branch])
        if fetch.returncode != 0:
            return fetch
        return self.runner.run(["git", "-C", str(checkout), "checkout", "-B", branch, f"origin/{branch}"])
