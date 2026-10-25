from shipsmith_agent.deployer import Deployer


class _QuietCollector:
    def info(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _deployer(monkeypatch, outputs):
    deployer = Deployer("/tmp/workdir", _QuietCollector())
    calls = []

    def fake_run(cmd, phase, **kwargs):
        calls.append(cmd)
        if "ps" in cmd:
            return 0, outputs["ps"]
        return 0, outputs["logs"]

    monkeypatch.setattr(deployer, "_run_command", fake_run)
    return deployer, calls


def test_collect_diagnostics_includes_state_and_each_service(monkeypatch):
    deployer, calls = _deployer(
        monkeypatch,
        {"ps": '[{"Service":"api","State":"running"}]', "logs": "line one\nline two"},
    )

    result = deployer.collect_diagnostics("docker-compose.yml", ["api", "worker"])

    assert "== docker compose ps ==" in result["content"]
    assert "== logs: api (last 200 lines) ==" in result["content"]
    assert "== logs: worker (last 200 lines) ==" in result["content"]
    assert result["truncated"] is False
    assert any("logs" in call and "api" in call for call in calls)


def test_collect_diagnostics_redacts_credentials(monkeypatch):
    deployer, _ = _deployer(
        monkeypatch,
        {
            "ps": "[]",
            "logs": "DATABASE_URL=postgresql://user:secret@db:5432/app\nAuthorization: Bearer tok123",
        },
    )

    result = deployer.collect_diagnostics("docker-compose.yml", ["api"])

    assert "secret" not in result["content"]
    assert "tok123" not in result["content"]
    assert "***" in result["content"]


def test_collect_diagnostics_caps_the_payload(monkeypatch):
    deployer, _ = _deployer(monkeypatch, {"ps": "[]", "logs": "y" * 100_000})

    result = deployer.collect_diagnostics("docker-compose.yml", ["api"], max_bytes=4096)

    assert result["truncated"] is True
    assert result["byte_size"] <= 4096 + 32
    assert "[truncated]" in result["content"]
