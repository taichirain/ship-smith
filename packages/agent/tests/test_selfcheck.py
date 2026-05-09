import os
import sys
import pytest
import json
from unittest.mock import patch, MagicMock
import io


sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)


class TestSelfCheck:
    def test_check_command_available_true(self):
        from shipsmith_agent.main import _check_command_available

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = _check_command_available("git")
            assert result is True
            mock_run.assert_called_once()

    def test_check_command_available_false(self):
        from shipsmith_agent.main import _check_command_available

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            result = _check_command_available("nonexistent")
            assert result is False

    def test_check_command_available_file_not_found(self):
        from shipsmith_agent.main import _check_command_available

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            result = _check_command_available("nonexistent")
            assert result is False

    def test_check_directory_writable_success(self, tmp_path):
        from shipsmith_agent.main import _check_directory_writable

        result = _check_directory_writable(str(tmp_path))
        assert result.passed is True
        assert tmp_path in result.message

    def test_check_directory_writable_not_exists(self):
        from shipsmith_agent.main import _check_directory_writable

        result = _check_directory_writable("/nonexistent/path/12345")
        assert result.passed is False

    def test_check_directory_writable_is_file(self, tmp_path):
        from shipsmith_agent.main import _check_directory_writable

        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        result = _check_directory_writable(str(test_file))
        assert result.passed is False

    def test_check_docker_daemon_success(self):
        from shipsmith_agent.main import _check_docker_daemon

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = _check_docker_daemon()
            assert result.passed is True
            assert "Docker daemon is running" in result.message

    def test_check_docker_daemon_failed(self):
        from shipsmith_agent.main import _check_docker_daemon

        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "Cannot connect to Docker daemon"
            mock_run.return_value = mock_result

            result = _check_docker_daemon()
            assert result.passed is False
            assert "not accessible" in result.message

    def test_run_selfcheck_all_pass(self, mock_settings):
        from shipsmith_agent.main import run_selfcheck, _check_command_available

        with patch("shipsmith_agent.main._check_command_available") as mock_cmd:
            with patch("shipsmith_agent.main._check_docker_daemon") as mock_docker:
                with patch("shipsmith_agent.main._check_directory_writable") as mock_dir:
                    with patch("shipsmith_agent.main._check_core_connectivity") as mock_core:
                        mock_cmd.return_value = True
                        mock_docker.return_value = MagicMock(passed=True, message="Docker OK", details=None)
                        mock_dir.return_value = MagicMock(passed=True, message="Dir OK", details=None)
                        mock_core.return_value = MagicMock(passed=True, message="Core OK", details=None)

                        with patch("sys.stdout", new=io.StringIO()) as fake_out:
                            result = run_selfcheck(output_json=True)
                            output = fake_out.getvalue()
                            parsed = json.loads(output)
                            assert result == 0
                            assert parsed["summary"]["passed"] >= 1

    def test_run_selfcheck_some_fail(self, mock_settings):
        from shipsmith_agent.main import run_selfcheck

        with patch("shipsmith_agent.main._check_command_available") as mock_cmd:
            with patch("shipsmith_agent.main._check_docker_daemon") as mock_docker:
                with patch("shipsmith_agent.main._check_directory_writable") as mock_dir:
                    with patch("shipsmith_agent.main._check_core_connectivity") as mock_core:
                        mock_cmd.side_effect = [True, False, False]
                        mock_docker.return_value = MagicMock(passed=False, message="Docker failed", details=None)
                        mock_dir.return_value = MagicMock(passed=False, message="Dir failed", details=None)
                        mock_core.return_value = MagicMock(passed=False, message="Core failed", details=None)

                        with patch("sys.stdout", new=io.StringIO()) as fake_out:
                            result = run_selfcheck(output_json=True)
                            output = fake_out.getvalue()
                            parsed = json.loads(output)
                            assert result == 1
                            assert parsed["summary"]["failed"] >= 1

    def test_run_selfcheck_text_output(self, mock_settings):
        from shipsmith_agent.main import run_selfcheck

        with patch("shipsmith_agent.main._check_command_available") as mock_cmd:
            with patch("shipsmith_agent.main._check_docker_daemon") as mock_docker:
                with patch("shipsmith_agent.main._check_directory_writable") as mock_dir:
                    with patch("shipsmith_agent.main._check_core_connectivity") as mock_core:
                        mock_cmd.return_value = True
                        mock_docker.return_value = MagicMock(passed=True, message="Docker OK", details=None)
                        mock_dir.return_value = MagicMock(passed=True, message="Dir OK", details=None)
                        mock_core.return_value = MagicMock(passed=True, message="Core OK", details=None)

                        with patch("sys.stdout", new=io.StringIO()) as fake_out:
                            result = run_selfcheck(output_json=False)
                            output = fake_out.getvalue()
                            assert result == 0
                            assert "ShipSmith Agent Self-Check" in output

    def test_show_help(self):
        from shipsmith_agent.main import show_help

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            show_help()
            output = fake_out.getvalue()
            assert "ShipSmith Agent" in output
            assert "selfcheck" in output
            assert "SHIPSMITH_AGENT_TOKEN" in output
