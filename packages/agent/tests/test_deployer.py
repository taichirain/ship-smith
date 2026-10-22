import subprocess

import pytest

from shipsmith_agent.deployer import Deployer, DeployError


class Collector:
    def __init__(self):
        self.events = []

    def info(self, phase, message):
        self.events.append((phase, message))

    def error(self, phase, message):
        self.events.append((phase, message))

    def emit(self, phase, message):
        self.events.append((phase, message))
        return True


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_repo(tmp_path, remote="https://github.com/test/repo.git"):
    repo = tmp_path / "workdir"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "app.txt").write_text("one\n", encoding="utf-8")
    git(repo, "add", "app.txt")
    git(repo, "commit", "-m", "one")
    git(repo, "branch", "-M", "main")
    git(repo, "remote", "add", "origin", remote)
    return repo


def make_deployer(repo, project_id=1):
    deployer = Deployer(str(repo), Collector(), project_id=project_id)
    deployer._write_marker("https://github.com/test/repo.git")
    return deployer


def test_missing_marker_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    deployer = Deployer(str(repo), Collector(), project_id=1)

    with pytest.raises(DeployError) as exc:
        deployer.ensure_repo("https://github.com/test/repo.git", "main")

    assert exc.value.error_code == "workdir_not_managed"


def test_dirty_workdir_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    (repo / "app.txt").write_text("two\n", encoding="utf-8")

    with pytest.raises(DeployError) as exc:
        deployer._assert_clean()

    assert exc.value.error_code == "workdir_dirty"


def test_workdir_project_mismatch_is_refused(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo, project_id=2)
    deployer.project_id = 1

    with pytest.raises(DeployError) as exc:
        deployer.ensure_repo("https://github.com/test/repo.git", "main")

    assert exc.value.error_code == "workdir_project_mismatch"


def test_non_empty_unmanaged_dir_is_refused(tmp_path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "notes.txt").write_text("mine\n", encoding="utf-8")
    deployer = Deployer(str(workdir), Collector(), project_id=1)

    with pytest.raises(DeployError) as exc:
        deployer.ensure_repo("https://github.com/test/repo.git", "main")

    assert exc.value.error_code == "workdir_not_empty"


def test_resolve_and_checkout(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    (repo / "app.txt").write_text("two\n", encoding="utf-8")
    git(repo, "add", "app.txt")
    git(repo, "commit", "-m", "two")
    second = git(repo, "rev-parse", "HEAD")
    deployer = make_deployer(repo)

    resolved = deployer.resolve_target("main", "main")
    assert resolved == second

    deployer.git_checkout_detached(first)
    assert git(repo, "rev-parse", "HEAD") == first


def test_deploy_refuses_dirty_before_checkout(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    (repo / "app.txt").write_text("dirty\n", encoding="utf-8")
    deployer.snapshot_runtime = lambda *args, **kwargs: {}

    with pytest.raises(DeployError) as exc:
        deployer.deploy(
            git_repo="https://github.com/test/repo.git",
            target_commit=None,
            branch="main",
            strategy="compose-build",
        )

    assert exc.value.error_code == "workdir_dirty"


def test_deploy_happy_path_mocked(tmp_path):
    repo = make_repo(tmp_path)
    first = git(repo, "rev-parse", "HEAD")
    (repo / "app.txt").write_text("two\n", encoding="utf-8")
    git(repo, "add", "app.txt")
    git(repo, "commit", "-m", "two")
    second = git(repo, "rev-parse", "HEAD")
    deployer = make_deployer(repo)

    deployer.git_fetch = lambda **kwargs: None
    deployer.snapshot_runtime = lambda *args, **kwargs: {}
    deployer.docker_compose_config = lambda *args, **kwargs: None
    deployer.docker_compose_build = lambda *args, **kwargs: None
    deployer.docker_compose_pull = lambda *args, **kwargs: None
    deployer.docker_compose_up = lambda *args, **kwargs: None

    result = deployer.deploy(
        git_repo="https://github.com/test/repo.git",
        target_commit=first,
        branch="main",
        strategy="compose-build",
        pre_deploy="echo pre-hook-ran",
        post_deploy="echo post-hook-ran",
    )

    assert result["commit"] == first
    assert result["previous_commit"] == second
    assert git(repo, "rev-parse", "HEAD") == first


def test_command_timeout(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)

    code, _ = deployer._run_command(
        ["bash", "-lc", "sleep 5"],
        phase="test_timeout",
        timeout=1,
    )

    assert code == 124


def test_command_output_is_redacted(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)

    code, output = deployer._run_command(
        ["bash", "-lc", "echo secret-token"],
        phase="test_redact",
        redact=["secret-token"],
        timeout=10,
    )

    assert code == 0
    assert "secret-token" not in output
    assert "***" in output
