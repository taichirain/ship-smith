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


def test_run_migration_uses_profiles_and_no_deps(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    deployer.compose_profiles = ["data-sync", "sync"]
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["cmd"] = cmd
        captured["phase"] = phase
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.run_migration(
        compose_file="docker-compose.yml",
        service="api",
        command="alembic upgrade head",
        timeout=120,
        no_deps=True,
    )

    assert captured["phase"] == "migration"
    assert captured["cmd"] == [
        "docker", "compose",
        "--profile", "data-sync",
        "--profile", "sync",
        "-f", "docker-compose.yml",
        "run", "--rm", "--no-deps",
        "api", "alembic", "upgrade", "head",
    ]


def test_migration_failure_stops_up(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    calls = []

    deployer.git_fetch = lambda **kwargs: None
    deployer.snapshot_runtime = lambda *args, **kwargs: {}
    deployer.docker_compose_config = lambda *args, **kwargs: calls.append("config")
    deployer.docker_compose_build = lambda *args, **kwargs: calls.append("build")
    deployer.docker_compose_up = lambda *args, **kwargs: calls.append("up")

    def fail_migration(**kwargs):
        calls.append("migration")
        raise DeployError("migration_failed", "migration failed")

    deployer.run_migration = fail_migration

    with pytest.raises(DeployError) as exc:
        deployer.deploy(
            git_repo="https://github.com/test/repo.git",
            target_commit=None,
            branch="main",
            strategy="compose-build",
            migration_service="api",
            migration_command="alembic upgrade head",
        )

    assert exc.value.error_code == "migration_failed"
    assert calls == ["config", "build", "migration"]


def test_deploy_lock_is_exclusive(tmp_path):
    repo = make_repo(tmp_path)
    first = make_deployer(repo)
    second = make_deployer(repo)

    with first._deploy_lock():
        with pytest.raises(DeployError) as exc:
            with second._deploy_lock():
                pass

    assert exc.value.error_code == "deploy_locked"


def test_docker_compose_up_includes_profiles(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    deployer.compose_profiles = ["data-sync"]
    captured = []

    def fake_run_command(cmd, phase, **kwargs):
        captured.append(cmd)
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_up("docker-compose.yml")

    assert captured[0] == [
        "docker", "compose",
        "--profile", "data-sync",
        "-f", "docker-compose.yml",
        "up", "-d",
    ]


def test_health_check_expected_status(monkeypatch):
    from shipsmith_agent.health_check import HealthChecker

    class FakeResponse:
        status_code = 204

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr("shipsmith_agent.health_check.httpx.Client", FakeClient)

    result = HealthChecker().check_http_health(
        "http://example.test/ready",
        timeout=2,
        expected_status=204,
    )

    assert result["status"] == "healthy"
    assert result["expected_status"] == 204


def test_build_uses_custom_timeout_and_cache_flag(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_build("docker-compose.yml", timeout=7200, no_cache=True)

    assert captured["timeout"] == 7200
    assert "--no-cache" in captured["cmd"]


def test_build_default_uses_cache(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["cmd"] = cmd
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_build("docker-compose.yml")

    assert "--no-cache" not in captured["cmd"]


def test_pull_uses_custom_timeout(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_pull("docker-compose.yml", timeout=3600)

    assert captured["timeout"] == 3600


def test_stop_uses_compose_stop(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["cmd"] = cmd
        captured["phase"] = phase
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_stop("docker-compose.yml")

    assert captured["phase"] == "service_stop"
    assert captured["cmd"][-1] == "stop"
    assert "--no-cache" not in captured["cmd"]


def test_stop_with_services_appends_them(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    captured = {}

    def fake_run_command(cmd, phase, **kwargs):
        captured["cmd"] = cmd
        return 0, ""

    deployer._run_command = fake_run_command
    deployer.docker_compose_stop("docker-compose.yml", services=["web", "worker"])

    assert captured["cmd"][-3:] == ["stop", "web", "worker"]


def _fake_backup_proc(monkeypatch, returncode=0, payload=b"dump-bytes", stderr=b""):
    import shipsmith_agent.deployer as deployer_mod

    class FakeProc:
        def __init__(self):
            self.returncode = returncode
            self.stderr = stderr

    def fake_run(cmd, cwd=None, env=None, stdout=None, stderr=None, timeout=None):
        stdout.write(payload)
        return FakeProc()

    monkeypatch.setattr(deployer_mod.subprocess, "run", fake_run)


def test_migration_backup_writes_stdout_to_file(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    _fake_backup_proc(monkeypatch, returncode=0, payload=b"pgdump-binary")

    path = deployer.run_migration_backup(
        "docker-compose.yml", service="db", command="pg_dump -Fc"
    )

    assert path is not None
    data = (tmp_path / "shipsmith-backups").glob("*-pre-migration.dump")
    files = list(data)
    assert len(files) == 1
    assert files[0].read_bytes() == b"pgdump-binary"


def test_migration_backup_requires_service(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)

    with pytest.raises(DeployError) as exc:
        deployer.run_migration_backup("docker-compose.yml", service="", command="pg_dump")

    assert exc.value.error_code == "migration_backup_service_missing"


def test_migration_backup_failure_aborts_and_cleans_up(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    _fake_backup_proc(monkeypatch, returncode=1, stderr=b"connection refused")

    with pytest.raises(DeployError) as exc:
        deployer.run_migration_backup("docker-compose.yml", service="db", command="pg_dump")

    assert exc.value.error_code == "migration_backup_failed"
    assert list((tmp_path / "shipsmith-backups").glob("*.dump")) == []


def test_migration_backup_skipped_without_command(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)

    assert deployer.run_migration_backup("docker-compose.yml", service="db", command=None) is None


def test_assert_managed_repo_rejects_uninitialized_dir(tmp_path):
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    deployer = Deployer(str(workdir), Collector(), project_id=1)

    with pytest.raises(DeployError) as exc:
        deployer.assert_managed_repo("https://github.com/test/repo.git")

    assert exc.value.error_code == "workdir_not_managed"


def test_assert_managed_repo_accepts_owned_dir(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)

    deployer.assert_managed_repo("https://github.com/test/repo.git")


def test_assert_managed_repo_rejects_foreign_project(tmp_path):
    repo = make_repo(tmp_path)
    deployer = make_deployer(repo)
    deployer.project_id = 99

    with pytest.raises(DeployError) as exc:
        deployer.assert_managed_repo("https://github.com/test/repo.git")

    assert exc.value.error_code == "workdir_project_mismatch"
