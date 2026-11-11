import json, os, subprocess, sys, threading, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages" / "agent"))
from shipsmith_agent.main import Agent
from shipsmith_agent.health_check import HealthChecker

root = Path("/tmp/shipsmith-monitor-smoke")
root.mkdir(exist_ok=True)
(root / "nginx.conf").write_text("server { listen 80; location / { return 200 'ok'; } }\n")
(root / "compose.yml").write_text("""name: shipsmith-monitor-smoke-20261111
services:
  api:
    image: nginx:alpine
    network_mode: bridge
    ports: ["127.0.0.1::80"]
    volumes: ["./nginx.conf:/etc/nginx/conf.d/default.conf:ro"]
  web:
    image: nginx:alpine
    network_mode: bridge
    ports: ["127.0.0.1::80"]
    volumes: ["./nginx.conf:/etc/nginx/conf.d/default.conf:ro"]
  old-worker:
    image: nginx:alpine
    network_mode: bridge
    profiles: [retired]
    command: ["true"]
""")
def compose(*args):
    return subprocess.check_output(["docker", "compose", "-f", "compose.yml", *args], cwd=root, text=True)
class Client:
    def send_heartbeat(self, payload):
        self.payload = payload
        return True
try:
    compose("up", "-d", "--pull", "never", "api", "web")
    urls = {s: "http://" + compose("port", s, "80").strip() + ("/ready" if s == "api" else "/") for s in ("api", "web")}
    checker = HealthChecker()
    for url in urls.values():
        assert checker.wait_http_health(url, timeout=8)["status"] == "healthy"
    agent = Agent.__new__(Agent)
    agent.settings = SimpleNamespace(workdir=str(root))
    agent.client = Client()
    agent.health_checker = checker
    checker.get_system_metrics = lambda: {}
    checker.get_runtime_info = lambda: {}
    agent._project_config = dict(deploy_workdir=str(root), compose_file="compose.yml", compose_profiles=[], healthcheck_url=urls["api"], healthcheck_urls=[urls["web"]], healthcheck_timeout_seconds=2, healthcheck_failure_threshold=2)
    agent._task_running = False
    agent._intentionally_stopped = False
    agent._health_lock = threading.Lock()
    agent._capture_health_diagnostics = lambda status: None
    def sample():
        agent._collect_and_send_heartbeat()
        return agent.client.payload["app_health"]
    assert sample()["status"] == "healthy"
    compose("stop", "web")
    first = sample()
    assert first["status"] == "unknown" and first["reason"] == "confirming_failure", first
    failed = sample()
    assert failed["status"] == "unhealthy", failed
    assert failed["checks"][0]["http_status"] == 200, failed
    assert "web" in failed["error"], failed
    compose("start", "web")
    urls["web"] = "http://" + compose("port", "web", "80").strip() + "/"
    agent._project_config["healthcheck_urls"] = [urls["web"]]
    assert checker.wait_http_health(urls["web"], timeout=8)["status"] == "healthy"
    recovered = sample()
    assert recovered["status"] == "healthy", recovered
    print(json.dumps(dict(result="PASS", api_stayed_healthy=True, states=["healthy", first["status"], failed["status"], recovered["status"]], failure_reason=failed["error"])))
finally:
    compose("down", "--remove-orphans")
