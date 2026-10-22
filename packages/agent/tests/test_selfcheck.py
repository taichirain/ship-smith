import io
import json
from unittest.mock import MagicMock, patch

from shipsmith_agent.self_check import (
    _check_command_available,
    _check_directory_writable,
    _check_docker_daemon,
)


def _precheck_result(status: str = "healthy") -> dict:
    healthy = status == "healthy"
    return {
        "agent_version": "0.1.0",
        "timestamp": 0,
        "overall_status": status,
        "summary": {
            "total": 1,
            "passed": 1 if healthy else 0,
            "failed": 0 if healthy else 1,
            "errors": 0 if healthy else 1,
            "warnings": 0,
        },
        "categories": {
            "tools": {
                "passed": 1 if healthy else 0,
                "failed": 0 if healthy else 1,
                "checks": [
                    {
                        "name": "git_available",
                        "category": "tools",
                        "passed": healthy,
                        "message": "Git CLI 可用" if healthy else "Git CLI 未安装",
                        "severity": "info" if healthy else "error",
                        "details": None,
                        "resolution": None,
                    }
                ],
            }
        },
        "checks": [],
    }


def test_check_command_available_true():
    with patch("shipsmith_agent.self_check.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        assert _check_command_available("git") is True


def test_check_command_available_false():
    with patch("shipsmith_agent.self_check.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        assert _check_command_available("nonexistent") is False


def test_check_command_available_file_not_found():
    with patch("shipsmith_agent.self_check.subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()

        assert _check_command_available("nonexistent") is False


def test_check_directory_writable_success(tmp_path):
    result = _check_directory_writable(str(tmp_path))
    assert result.passed is True
    assert str(tmp_path) in result.message


def test_check_directory_writable_not_exists():
    result = _check_directory_writable("/nonexistent/path/12345")
    assert result.passed is False


def test_check_directory_writable_is_file(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")

    result = _check_directory_writable(str(test_file))
    assert result.passed is False


def test_check_docker_daemon_success():
    with patch("shipsmith_agent.self_check.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = _check_docker_daemon()
        assert result.passed is True


def test_check_docker_daemon_failed():
    with patch("shipsmith_agent.self_check.subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Cannot connect to Docker daemon"
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        result = _check_docker_daemon()
        assert result.passed is False


def test_run_selfcheck_all_pass():
    from shipsmith_agent.main import run_selfcheck

    with patch("shipsmith_agent.main.run_precheck", return_value=_precheck_result("healthy")):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            result = run_selfcheck(output_json=True)
            parsed = json.loads(fake_out.getvalue())

    assert result == 0
    assert parsed["summary"]["passed"] == 1


def test_run_selfcheck_some_fail():
    from shipsmith_agent.main import run_selfcheck

    with patch("shipsmith_agent.main.run_precheck", return_value=_precheck_result("unhealthy")):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            result = run_selfcheck(output_json=True)
            parsed = json.loads(fake_out.getvalue())

    assert result == 1
    assert parsed["summary"]["failed"] == 1


def test_run_selfcheck_text_output():
    from shipsmith_agent.main import run_selfcheck

    with patch("shipsmith_agent.main.run_precheck", return_value=_precheck_result("healthy")):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            result = run_selfcheck(output_json=False)
            output = fake_out.getvalue()

    assert result == 0
    assert "ShipSmith Agent" in output


def test_show_help():
    from shipsmith_agent.main import show_help

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        show_help()
        output = fake_out.getvalue()

    assert "ShipSmith Agent" in output
    assert "selfcheck" in output
    assert "SHIPSMITH_AGENT_TOKEN" in output
