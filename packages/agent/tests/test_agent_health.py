import threading
from types import SimpleNamespace

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
