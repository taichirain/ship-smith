import threading
import json
from types import SimpleNamespace

from shipsmith_agent.health_check import HealthChecker, derive_container_health
from shipsmith_agent.main import Agent


class FakeClient:
    def __init__(self):
        self.payload = None
        self.config = {
            "healthcheck_url": "http://127.0.0.1:8080/ready",
            "healthcheck_timeout_seconds": 3,
            "healthcheck_expected_status": 204,
        }

    def get_agent_config(self):
        return self.config

    def send_heartbeat(self, payload):
        self.payload = payload
        return True


class FakeHealth:
    def __init__(self):
        self.last_args = None
        self.container_args = None

    def get_system_metrics(self):
        return {}

    def get_container_statuses(self, workdir, compose_file, compose_profiles=None):
        self.container_args = (workdir, compose_file, compose_profiles)
        return [{"service": "api", "status": "running", "health": "healthy"}]

    def get_runtime_info(self):
        return {}

    def check_http_health(self, url, timeout=10, expected_status=200):
        self.last_args = (url, timeout, expected_status)
        return {
            "status": "healthy",
            "http_status": expected_status,
            "expected_status": expected_status,
        }


def make_agent(task_running=False):
    agent = Agent.__new__(Agent)
    agent.settings = SimpleNamespace(workdir="/opt/test")
    agent.client = FakeClient()
    agent.health_checker = FakeHealth()
    agent._project_config = {
        "deploy_workdir": "/opt/test",
        "healthcheck_url": "http://127.0.0.1:8080/ready",
        "healthcheck_timeout_seconds": 3,
        "healthcheck_expected_status": 204,
        "compose_file": "deploy/compose.yml",
        "compose_profiles": ["scheduler"],
    }
    agent._task_running = task_running
    agent._health_lock = threading.Lock()
    agent._intentionally_stopped = False
    return agent


def test_heartbeat_uses_project_health_config():
    agent = make_agent()

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["app_health"]["status"] == "healthy"
    assert agent.health_checker.last_args == (
        "http://127.0.0.1:8080/ready",
        3,
        204,
    )
    assert agent.health_checker.container_args == (
        "/opt/test",
        "deploy/compose.yml",
        ["scheduler"],
    )


def test_heartbeat_skips_health_during_deployment():
    agent = make_agent(task_running=True)

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["app_health"]["status"] == "unknown"
    assert agent.client.payload["app_health"]["reason"] == "deployment_in_progress"
    assert agent.health_checker.last_args is None


def test_heartbeat_skips_container_snapshot_when_workdir_mismatches():
    agent = make_agent()
    agent._project_config["deploy_workdir"] = "/opt/different-project"

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["containers"] == []
    assert agent.health_checker.container_args is None


def test_refresh_project_config():
    agent = make_agent()
    agent._project_config = None

    agent._refresh_project_config()

    assert agent._project_config["healthcheck_expected_status"] == 204


def test_container_statuses_are_scoped_to_compose_project(tmp_path, monkeypatch):
    compose_dir = tmp_path / "deploy"
    compose_dir.mkdir()
    (compose_dir / "compose.yml").write_text("services: {}\n")
    commands = []

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        if command[-2:] == ["config", "--services"]:
            return SimpleNamespace(returncode=0, stdout="web\n", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "Name": "training-stage-web-1",
                "Service": "web",
                "State": "running",
                "Image": "training:stage",
                "Ports": "127.0.0.1:18191->80/tcp",
                "Labels": f"com.docker.compose.project.config_files={compose_dir / 'compose.yml'}",
            }),
            stderr="",
        )

    monkeypatch.setattr("shipsmith_agent.health_check.subprocess.run", fake_run)
    result = HealthChecker().get_container_statuses(str(tmp_path), "deploy/compose.yml", ["scheduler"])

    assert result == [{
        "service": "training-stage-web-1",
        "status": "running",
        "image": "training:stage",
        "ports": ["127.0.0.1:18191->80/tcp"],
        "health": None,
    }]
    assert commands[0][0] == [
        "docker", "compose", "--profile", "scheduler", "-f", "deploy/compose.yml",
        "ps", "--all", "--orphans=false", "--format", "json",
    ]
    assert commands[0][1]["cwd"] == str(tmp_path)


def test_container_statuses_never_fall_back_to_host_docker_ps(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr("shipsmith_agent.health_check.subprocess.run", lambda *args, **kwargs: commands.append(args))

    assert HealthChecker().get_container_statuses(str(tmp_path), "missing.yml") == []
    assert HealthChecker().get_container_statuses(str(tmp_path), None) == []
    assert commands == []


def test_container_statuses_rejects_same_compose_name_from_other_workdir(tmp_path, monkeypatch):
    (tmp_path / "compose.yml").write_text("name: shared-name\nservices: {}\n")
    monkeypatch.setattr(
        "shipsmith_agent.health_check.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="web\n" if args[0][-2:] == ["config", "--services"] else json.dumps({
                "Name": "production-web-1",
                "State": "running",
                "Labels": "com.docker.compose.project.config_files=/opt/production/compose.yml",
            }),
            stderr="",
        ),
    )

    assert HealthChecker().get_container_statuses(str(tmp_path), "compose.yml") == [{"service": "web", "status": "missing", "health": None}]


def test_container_statuses_accept_newline_delimited_compose_json(tmp_path, monkeypatch):
    (tmp_path / "compose.yml").write_text("services: {}\n")
    config_label = f"com.docker.compose.project.config_files={tmp_path / 'compose.yml'}"
    output = "\n".join(json.dumps(row) for row in (
        {"Name": "api-1", "Service": "api", "State": "running", "Ports": "", "Labels": config_label},
        {"Name": "web-1", "Service": "web", "State": "running", "Ports": "", "Labels": config_label},
        {"Name": "migration-run-1", "State": "exited", "Labels": f"{config_label},com.docker.compose.oneoff=True"},
    ))
    monkeypatch.setattr(
        "shipsmith_agent.health_check.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="api\nweb\n" if args[0][-2:] == ["config", "--services"] else output, stderr=""),
    )

    result = HealthChecker().get_container_statuses(str(tmp_path), "compose.yml")

    assert [item["service"] for item in result] == ["api-1", "web-1"]


def test_deployment_health_waits_for_service_start(monkeypatch):
    checker = HealthChecker()
    attempts = []

    def check(url, timeout, expected_status):
        attempts.append((url, expected_status))
        if len(attempts) == 1:
            return {"status": "unhealthy", "error": "connection refused"}
        return {"status": "healthy", "http_status": expected_status}

    monkeypatch.setattr(checker, "check_http_health", check)

    result = checker.wait_http_health("http://stage/ready", timeout=3, expected_status=204, interval=0)

    assert result == {"status": "healthy", "http_status": 204}
    assert attempts == [("http://stage/ready", 204), ("http://stage/ready", 204)]


def test_deployment_health_rejects_service_after_deadline(monkeypatch):
    checker = HealthChecker()
    monkeypatch.setattr(
        checker,
        "check_http_health",
        lambda url, timeout, expected_status: {"status": "unhealthy", "http_status": 503},
    )

    result = checker.wait_http_health("http://stage/ready", timeout=0, interval=0)

    assert result == {"status": "unhealthy", "http_status": 503}


def test_heartbeat_reports_stopped_when_intentionally_stopped():
    agent = make_agent()
    agent._intentionally_stopped = True

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["app_health"]["status"] == "stopped"


def test_heartbeat_reports_stopped_from_project_config():
    agent = make_agent()
    agent._project_config["intentionally_stopped"] = True

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["app_health"]["status"] == "stopped"


def test_derive_container_health_without_containers():
    assert derive_container_health([]) == "unknown"


def test_derive_container_health_all_running():
    containers = [
        {"service": "api", "status": "running", "health": "healthy"},
        {"service": "web", "status": "running", "health": None},
    ]
    assert derive_container_health(containers) == "healthy"


def test_derive_container_health_unhealthy_container():
    containers = [{"service": "api", "status": "running", "health": "unhealthy"}]
    assert derive_container_health(containers) == "unhealthy"


def test_derive_container_health_still_starting():
    containers = [{"service": "api", "status": "running", "health": "starting"}]
    assert derive_container_health(containers) == "unknown"


def test_derive_container_health_exited_or_restarting():
    assert derive_container_health([{"service": "api", "status": "exited", "health": None}]) == "unhealthy"
    assert derive_container_health([{"service": "api", "status": "restarting", "health": None}]) == "unhealthy"


def test_api_healthy_does_not_hide_exited_frontend():
    agent = make_agent()
    agent.health_checker.get_container_statuses = lambda **kwargs: [
        {"service": "api", "status": "running", "health": "healthy"},
        {"service": "web", "status": "exited", "health": "unhealthy"},
    ]
    agent._capture_health_diagnostics = lambda status: None
    agent._collect_and_send_heartbeat()
    assert agent.client.payload["app_health"]["status"] == "unknown"
    assert agent.client.payload["app_health"]["reason"] == "confirming_failure"
    agent._collect_and_send_heartbeat()
    health = agent.client.payload["app_health"]
    assert health["status"] == "unhealthy"
    assert "web" in health["error"]
    assert health["http_status"] == 204


def test_all_http_probes_are_required_and_failure_count_resets():
    agent = make_agent()
    agent._capture_health_diagnostics = lambda status: None
    agent._project_config["healthcheck_urls"] = ["http://frontend/", "http://frontend/"]
    calls = []
    frontend_ok = False

    def check(url, **kwargs):
        calls.append(url)
        code = 204 if "ready" in url or frontend_ok else 502
        return {"status": "healthy" if code == 204 else "unhealthy", "http_status": code}

    agent.health_checker.check_http_health = check
    agent._collect_and_send_heartbeat()
    agent._collect_and_send_heartbeat()
    health = agent.client.payload["app_health"]
    assert health["status"] == "unhealthy"
    assert len(health["checks"]) == 2
    assert "http://frontend/: HTTP 502" in health["error"]
    assert calls.count("http://frontend/") == 2
    frontend_ok = True
    agent._collect_and_send_heartbeat()
    assert agent.client.payload["app_health"]["status"] == "healthy"
    frontend_ok = False
    agent._collect_and_send_heartbeat()
    assert agent.client.payload["app_health"]["status"] == "unknown"
    assert agent.client.payload["app_health"]["consecutive_failures"] == 1


def test_missing_or_unreadable_container_snapshot_never_reports_healthy():
    agent = make_agent()
    agent.health_checker.get_container_statuses = lambda **kwargs: []
    agent._collect_and_send_heartbeat()
    assert agent.client.payload["app_health"]["status"] == "unknown"


def test_http_failure_is_not_hidden_by_starting_container():
    agent = make_agent()
    agent._project_config["healthcheck_failure_threshold"] = 1
    agent._capture_health_diagnostics = lambda status: None
    agent.health_checker.get_container_statuses = lambda **kwargs: [
        {"service": "web", "status": "running", "health": "starting"},
    ]
    agent.health_checker.check_http_health = lambda *args, **kwargs: {"status": "unhealthy", "http_status": 502}
    agent._collect_and_send_heartbeat()
    assert agent.client.payload["app_health"]["status"] == "unhealthy"


def test_only_enabled_services_are_required_and_missing_services_detected(tmp_path, monkeypatch):
    (tmp_path / "compose.yml").write_text("services: {}\n")
    labels = {"com.docker.compose.project.config_files": str(tmp_path / "compose.yml")}
    rows = [
        {"Name": "api-1", "Service": "api", "State": "running", "Labels": labels},
        {"Name": "old-worker-1", "Service": "worker", "State": "exited", "Labels": labels},
        {"Name": "migrate-1", "Service": "migrate", "State": "exited", "Labels": dict(labels, **{"com.docker.compose.oneoff": "True"})},
    ]
    monkeypatch.setattr("shipsmith_agent.health_check.subprocess.run", lambda command, **kwargs: SimpleNamespace(
        returncode=0, stderr="", stdout="api\nweb\nworker-light\n" if command[-2:] == ["config", "--services"] else json.dumps(rows),
    ))
    containers = HealthChecker().get_container_statuses(str(tmp_path), "compose.yml", ["light-workers"])
    assert {c["service"] for c in containers} == {"api-1", "web", "worker-light"}
    assert derive_container_health(containers) == "unhealthy"
