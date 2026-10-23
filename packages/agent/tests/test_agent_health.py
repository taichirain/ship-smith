import threading
from types import SimpleNamespace

from shipsmith_agent.health_check import HealthChecker
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

    def get_system_metrics(self):
        return {}

    def get_container_statuses(self):
        return []

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
    agent.settings = SimpleNamespace()
    agent.client = FakeClient()
    agent.health_checker = FakeHealth()
    agent._project_config = {
        "healthcheck_url": "http://127.0.0.1:8080/ready",
        "healthcheck_timeout_seconds": 3,
        "healthcheck_expected_status": 204,
    }
    agent._task_running = task_running
    agent._health_lock = threading.Lock()
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


def test_heartbeat_skips_health_during_deployment():
    agent = make_agent(task_running=True)

    agent._collect_and_send_heartbeat()

    assert agent.client.payload["app_health"]["status"] == "unknown"
    assert agent.client.payload["app_health"]["reason"] == "deployment_in_progress"
    assert agent.health_checker.last_args is None


def test_refresh_project_config():
    agent = make_agent()
    agent._project_config = None

    agent._refresh_project_config()

    assert agent._project_config["healthcheck_expected_status"] == 204


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
