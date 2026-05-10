import logging
import os
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

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

    def _run_command(
        self,
        cmd: list,
        phase: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        redact: Optional[list[str]] = None,
    ) -> Tuple[int, str]:
        effective_cwd = cwd or self.workdir
        display_cmd = " ".join(cmd)
        for secret in redact or []:
            if secret:
                display_cmd = display_cmd.replace(secret, "***")
        self.log_collector.info(phase, f"$ {display_cmd}")

        try:
            result = subprocess.run(
                cmd,
                cwd=effective_cwd,
                capture_output=True,
                text=True,
                env=env,
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

    def _prepare_git_auth(
        self,
        git_repo: Optional[str],
        git_credential_type: str = "none",
        git_credential_username: Optional[str] = None,
        git_credential_token: Optional[str] = None,
        git_credential_ssh_private_key: Optional[str] = None,
        git_credential_ssh_known_hosts: Optional[str] = None,
    ) -> Dict[str, Any]:
        env = os.environ.copy()
        repo = (git_repo or "").strip()
        cleanup_paths: list[Path] = []
        redact: list[str] = []

        if git_credential_type == "http_token" and git_credential_token and repo.startswith(("http://", "https://")):
            from urllib.parse import urlparse, urlunparse, quote

            parsed = urlparse(repo)
            username = quote((git_credential_username or "git").strip(), safe="")
            token = quote(git_credential_token.strip(), safe="")
            netloc = f"{username}:{token}@{parsed.hostname or ''}"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            repo = urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            redact.append(git_credential_token.strip())

        if git_credential_type == "ssh_key" and git_credential_ssh_private_key:
            ssh_root = Path(tempfile.mkdtemp(prefix="shipsmith-agent-ssh-"))
            cleanup_paths.append(ssh_root)
            key_path = ssh_root / "id_repo"
            key_path.write_text(git_credential_ssh_private_key.strip() + "\n", encoding="utf-8")
            key_path.chmod(0o600)

            known_hosts_path = ssh_root / "known_hosts"
            known_hosts_value = (git_credential_ssh_known_hosts or "").strip()
            if known_hosts_value:
                known_hosts_path.write_text(known_hosts_value + "\n", encoding="utf-8")
                strict_host = "yes"
            else:
                known_hosts_path.touch(mode=0o600)
                strict_host = "accept-new"

            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key_path} -o IdentitiesOnly=yes "
                f"-o UserKnownHostsFile={known_hosts_path} "
                f"-o StrictHostKeyChecking={strict_host}"
            )

        return {
            "repo": repo,
            "env": env,
            "cleanup_paths": cleanup_paths,
            "redact": redact,
        }

    def _cleanup_git_auth(self, cleanup_paths: list[Path]) -> None:
        for path in cleanup_paths:
            try:
                if path.is_dir():
                    for child in sorted(path.rglob("*"), reverse=True):
                        if child.is_file() or child.is_symlink():
                            child.unlink(missing_ok=True)
                        elif child.is_dir():
                            child.rmdir()
                    path.rmdir()
            except Exception:
                pass

    def ensure_repo(
        self,
        git_repo: str,
        branch: str,
        git_credential_type: str = "none",
        git_credential_username: Optional[str] = None,
        git_credential_token: Optional[str] = None,
        git_credential_ssh_private_key: Optional[str] = None,
        git_credential_ssh_known_hosts: Optional[str] = None,
    ) -> Dict[str, Any]:
        auth = self._prepare_git_auth(
            git_repo=git_repo,
            git_credential_type=git_credential_type,
            git_credential_username=git_credential_username,
            git_credential_token=git_credential_token,
            git_credential_ssh_private_key=git_credential_ssh_private_key,
            git_credential_ssh_known_hosts=git_credential_ssh_known_hosts,
        )
        repo_dir = Path(self.workdir)
        git_dir = repo_dir / ".git"
        if git_dir.exists():
            return auth

        repo_dir.mkdir(parents=True, exist_ok=True)
        code, _ = self._run_command(
            ["git", "clone", "--branch", branch, "--single-branch", auth["repo"], self.workdir],
            phase="git_clone",
            cwd=str(repo_dir.parent),
            env=auth["env"],
            redact=auth["redact"],
        )
        if code != 0:
            self._cleanup_git_auth(auth["cleanup_paths"])
            raise DeployError("git_clone_failed", "git clone failed")
        return auth

    def git_fetch(self, env: Optional[Dict[str, str]] = None, redact: Optional[list[str]] = None) -> None:
        code, _ = self._run_command(
            ["git", "fetch", "--all", "--prune"],
            phase="git_fetch",
            env=env,
            redact=redact,
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
        git_repo: str,
        target_commit: Optional[str],
        branch: str,
        strategy: str,
        git_credential_type: str = "none",
        git_credential_username: Optional[str] = None,
        git_credential_token: Optional[str] = None,
        git_credential_ssh_private_key: Optional[str] = None,
        git_credential_ssh_known_hosts: Optional[str] = None,
        compose_file: str = "docker-compose.yml",
        pre_deploy: Optional[str] = None,
        post_deploy: Optional[str] = None,
) -> str:
        self.log_collector.info("git_fetch", "Starting deployment...")
        auth = self.ensure_repo(
            git_repo=git_repo,
            branch=branch,
            git_credential_type=git_credential_type,
            git_credential_username=git_credential_username,
            git_credential_token=git_credential_token,
            git_credential_ssh_private_key=git_credential_ssh_private_key,
            git_credential_ssh_known_hosts=git_credential_ssh_known_hosts,
        )
        try:
            self.git_fetch(env=auth["env"], redact=auth["redact"])

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
        finally:
            self._cleanup_git_auth(auth["cleanup_paths"])
