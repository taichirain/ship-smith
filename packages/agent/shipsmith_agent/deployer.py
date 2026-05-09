import logging
import os
import subprocess
import time
from typing import Optional, Tuple

from .log_collector import LogCollector


logger = logging.getLogger(__name__)


class DeployError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class Deployer:
    def __init__(self, workdir: str, log_collector: LogCollector):
        self.workdir = workdir
        self.log_collector = log_collector

    def _run_command(self, cmd: list, phase: str, cwd: Optional[str] = None) -> Tuple[int, str]:
        effective_cwd = cwd or self.workdir
        self.log_collector.info(phase, f"$ {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=effective_cwd,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as e:
            self.log_collector.error(phase, f"Command not found: {e}")
            return -1, str(e)
        except Exception as e:
            self.log_collector.error(phase, f"Failed to execute command: {e}")
            return -1, str(e)

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line:
                    self.log_collector.emit(phase, line)
        if result.stderr:
            for line in result.stderr.strip().split("\n"):
                if line:
                    self.log_collector.emit(phase, line)

        return result.returncode, result.stdout + result.stderr

    def git_fetch(self) -> None:
        code, _ = self._run_command(
            ["git", "fetch", "--all", "--prune"],
            phase="git_fetch",
        )
        if code != 0:
            raise DeployError("git_fetch_failed", "git fetch failed")

    def git_checkout(self, target: str) -> None:
        code, _ = self._run_command(
            ["git", "checkout", target],
            phase="git_checkout",
        )
        if code != 0:
            raise DeployError("git_checkout_failed", f"git checkout failed")

    def git_reset(self, target: str) -> None:
        code, _ = self._run_command(
            ["git", "reset", "--hard", target],
            phase="git_reset",
        )
        if code != 0:
            raise DeployError("git_reset_failed", "git reset failed")

    def get_current_commit(self) -> str:
        code, output = self._run_command(
            ["git", "rev-parse", "HEAD"],
            phase="git_checkout",
        )
        if code != 0:
            raise DeployError("git_checkout_failed", "Failed to get current commit")
        return output.strip()

    def docker_compose_build(self, compose_file: str = "docker-compose.yml") -> None:
        code, _ = self._run_command(
            ["docker", "compose", "-f", compose_file, "build"],
            phase="docker_build",
        )
        if code != 0:
            raise DeployError("docker_build_failed", "docker compose build failed")

    def docker_compose_pull(self, compose_file: str = "docker-compose.yml") -> None:
        code, _ = self._run_command(
            ["docker", "compose", "-f", compose_file, "pull"],
            phase="docker_pull",
        )
        if code != 0:
            raise DeployError("docker_pull_failed", "docker compose pull failed")

    def docker_compose_up(self, compose_file: str = "docker-compose.yml") -> None:
        code, _ = self._run_command(
            ["docker", "compose", "-f", compose_file, "up", "-d"],
            phase="docker_up",
        )
        if code != 0:
            raise DeployError("docker_up_failed", "docker compose up failed")

    def run_pre_deploy(self, cmd: Optional[str]) -> None:
        if not cmd or not cmd.strip():
            return

        code, _ = self._run_command(
            ["bash", "-c", cmd],
            phase="pre_deploy",
        )
        if code != 0:
            raise DeployError("pre_deploy_failed", "pre_deploy command failed")

    def run_post_deploy(self, cmd: Optional[str]) -> None:
        if not cmd or not cmd.strip():
            return

        code, _ = self._run_command(
            ["bash", "-c", cmd],
            phase="post_deploy",
        )
        if code != 0:
            raise DeployError("post_deploy_failed", "post_deploy command failed")

    def deploy(
        self,
        target_commit: Optional[str],
        branch: str,
        strategy: str,
        compose_file: str = "docker-compose.yml",
        pre_deploy: Optional[str] = None,
        post_deploy: Optional[str] = None,
) -> str:
        self.log_collector.info("git_fetch", "Starting deployment...")

        self.git_fetch()

        target = target_commit or branch
        self.log_collector.info("git_checkout", f"Checking out: {target}")
        self.git_checkout(target)

        self.git_reset(target)

        self.log_collector.info("git_reset", f"Target reset to: {target}")

        current_commit = self.get_current_commit()
        self.log_collector.info("git_reset", f"Current commit: {current_commit}")

        self.run_pre_deploy(pre_deploy)

        if strategy == "compose-build":
            self.docker_compose_build(compose_file)
        elif strategy == "compose-pull":
            self.docker_compose_pull(compose_file)

        self.docker_compose_up(compose_file)

        self.run_post_deploy(post_deploy)

        return current_commit
