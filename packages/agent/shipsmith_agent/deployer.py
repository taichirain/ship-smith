import json
import logging
import os
import re
import signal
import subprocess
import threading
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from .log_collector import LogCollector


logger = logging.getLogger(__name__)

MANAGED_DIR = ".shipsmith"
MANAGED_MARKER = "project.json"

DEFAULT_TIMEOUTS = {
    "git_clone": 600,
    "git_fetch": 300,
    "git_state": 60,
    "git_resolve": 60,
    "git_checkout": 120,
    "git_reset": 120,
    "docker_config": 120,
    "docker_build": 1800,
    "docker_pull": 900,
    "docker_up": 300,
    "pre_deploy": 600,
    "post_deploy": 600,
    "snapshot": 60,
}

FORBIDDEN_WORKDIRS = {
    "/",
    "/home",
    "/root",
    "/opt",
    "/usr",
    "/var",
    "/etc",
    "/tmp",
    "/srv",
}


class DeployError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


def _normalize_repo_url(repo_url: str) -> str:
    value = (repo_url or "").strip().lower()
    if not value:
        return ""

    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        value = f"{host}/{path}"
    elif "://" in value:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        value = f"{parsed.hostname or ''}{parsed.path}"

    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    return value


class Deployer:
    def __init__(self, workdir: str, log_collector: LogCollector, project_id: Optional[int] = None):
        self.workdir = os.path.abspath(workdir) if workdir else ""
        self.log_collector = log_collector
        self.project_id = project_id

    # ------------------------------------------------------------------
    # command execution
    # ------------------------------------------------------------------
    def _redact(self, text: str, secrets: Optional[List[str]] = None) -> str:
        value = text or ""
        for secret in secrets or []:
            if secret:
                value = value.replace(secret, "***")

        value = re.sub(
            r"(?i)(https?://[^\s/@:]+:)[^@\s]+@",
            r"\1***@",
            value,
        )
        value = re.sub(
            r"(?i)(authorization:\s*bearer\s+)\S+",
            r"\1***",
            value,
        )
        value = re.sub(
            r"(?i)([?&](?:token|access_token|private_token)=)[^&\s]+",
            r"\1***",
            value,
        )
        return value

    def _run_command(
        self,
        cmd: list,
        phase: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        redact: Optional[list] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, str]:
        effective_cwd = cwd or self.workdir
        display_cmd = self._redact(" ".join(str(part) for part in cmd), redact)
        self.log_collector.info(phase, f"$ {display_cmd}")

        command_env = os.environ.copy()
        command_env.setdefault("GIT_TERMINAL_PROMPT", "0")
        command_env.setdefault("GIT_ASKPASS", "/bin/true")
        if env:
            command_env.update(env)

        effective_timeout = timeout or DEFAULT_TIMEOUTS.get(phase, 600)
        output_lines: List[str] = []

        try:
            process = subprocess.Popen(
                cmd,
                cwd=effective_cwd,
                env=command_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            self.log_collector.error(phase, f"Command not found: {exc}")
            return -1, str(exc)
        except Exception as exc:
            self.log_collector.error(phase, f"Failed to execute command: {exc}")
            return -1, str(exc)

        def read_output() -> None:
            try:
                if process.stdout is None:
                    return
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\n")
                    if not line:
                        continue
                    safe_line = self._redact(line, redact)
                    output_lines.append(safe_line)
                    self.log_collector.emit(phase, safe_line)
            except Exception as exc:
                logger.debug("failed to read command output for %s: %s", phase, exc)
            finally:
                try:
                    if process.stdout is not None:
                        process.stdout.close()
                except Exception:
                    pass

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()

        try:
            return_code = process.wait(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            self.log_collector.error(
                phase,
                f"Command timed out after {effective_timeout}s: {display_cmd}",
            )
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except Exception:
                try:
                    process.terminate()
                except Exception:
                    pass
            try:
                process.wait(timeout=5)
            except Exception:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
            try:
                if process.stdout is not None:
                    process.stdout.close()
            except Exception:
                pass
            reader.join(timeout=2)
            return 124, "\n".join(output_lines)

        reader.join(timeout=2)
        return return_code, "\n".join(output_lines)

    # ------------------------------------------------------------------
    # workdir ownership and repository state
    # ------------------------------------------------------------------
    def _marker_path(self) -> Path:
        return Path(self.workdir) / MANAGED_DIR / MANAGED_MARKER

    def _write_marker(self, git_repo: str) -> None:
        marker_path = self._marker_path()
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": 1,
            "project_id": self.project_id,
            "git_repo": git_repo,
            "managed_by": "shipsmith-agent",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp_path = marker_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, marker_path)

        exclude_path = Path(self.workdir) / ".git" / "info" / "exclude"
        try:
            exclude_path.parent.mkdir(parents=True, exist_ok=True)
            existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
            if f"{MANAGED_DIR}/" not in existing.splitlines():
                with exclude_path.open("a", encoding="utf-8") as handle:
                    if existing and not existing.endswith("\n"):
                        handle.write("\n")
                    handle.write(f"{MANAGED_DIR}/\n")
        except Exception as exc:
            logger.warning("failed to update git exclude file: %s", exc)

    def _validate_marker(self, git_repo: str) -> None:
        marker_path = self._marker_path()
        if not marker_path.exists():
            raise DeployError(
                "workdir_not_managed",
                f"Deploy workdir is not managed by ShipSmith: {self.workdir}. "
                "Adopt it explicitly before deploying.",
            )
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DeployError("workdir_marker_invalid", f"Invalid workdir marker: {exc}")

        if payload.get("project_id") != self.project_id:
            raise DeployError(
                "workdir_project_mismatch",
                f"Workdir belongs to project {payload.get('project_id')}, not {self.project_id}",
            )
        if _normalize_repo_url(payload.get("git_repo", "")) != _normalize_repo_url(git_repo):
            raise DeployError(
                "workdir_repo_mismatch",
                "Workdir marker repository does not match the project repository",
            )

    def _assert_workdir_is_safe(self) -> None:
        if not self.workdir:
            raise DeployError("workdir_missing", "Deploy workdir is empty")
        if not os.path.isabs(self.workdir):
            raise DeployError("workdir_not_absolute", "Deploy workdir must be absolute")
        if self.workdir in FORBIDDEN_WORKDIRS:
            raise DeployError("workdir_forbidden", f"Refusing to deploy into {self.workdir}")

    def _remote_url(self, env: Optional[Dict[str, str]] = None) -> str:
        code, output = self._run_command(
            ["git", "config", "--get", "remote.origin.url"],
            phase="git_state",
            env=env,
            timeout=60,
        )
        if code != 0:
            raise DeployError("git_remote_missing", "Git remote origin is not configured")
        return output.strip().splitlines()[-1].strip() if output.strip() else ""

    def _assert_remote_matches(self, git_repo: str, env: Optional[Dict[str, str]] = None) -> None:
        remote = self._remote_url(env=env)
        if _normalize_repo_url(remote) != _normalize_repo_url(git_repo):
            raise DeployError(
                "git_remote_mismatch",
                f"Workdir remote does not match project repository: {remote}",
            )

    def _assert_clean(self) -> None:
        code, output = self._run_command(
            ["git", "status", "--porcelain"],
            phase="git_state",
            timeout=60,
        )
        if code != 0:
            raise DeployError("git_status_failed", "Failed to inspect workdir status")
        if output.strip():
            preview = "\n".join(output.strip().splitlines()[:20])
            raise DeployError(
                "workdir_dirty",
                "Deploy workdir has local changes. Commit, stash or remove them before deploying.\n"
                f"{preview}",
            )

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
        self._assert_workdir_is_safe()
        if not self.project_id:
            raise DeployError("project_id_missing", "Agent task did not include a project id")

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
            self._validate_marker(git_repo)
            self._assert_remote_matches(git_repo, env=auth["env"])
            return auth

        if repo_dir.exists() and any(repo_dir.iterdir()):
            raise DeployError(
                "workdir_not_empty",
                f"Refusing to clone into non-empty directory: {self.workdir}",
            )

        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        code, _ = self._run_command(
            ["git", "clone", "--branch", branch, auth["repo"], self.workdir],
            phase="git_clone",
            cwd=str(repo_dir.parent),
            env=auth["env"],
            redact=auth["redact"],
        )
        if code != 0:
            raise DeployError("git_clone_failed", "git clone failed")

        self._write_marker(git_repo)
        self._assert_remote_matches(git_repo, env=auth["env"])
        return auth

    def git_fetch(self, env: Optional[Dict[str, str]] = None, redact: Optional[list] = None) -> None:
        code, _ = self._run_command(
            ["git", "fetch", "--all", "--prune", "--tags"],
            phase="git_fetch",
            env=env,
            redact=redact,
        )
        if code != 0:
            raise DeployError("git_fetch_failed", "git fetch failed")

    def get_current_commit(self) -> Optional[str]:
        code, output = self._run_command(
            ["git", "rev-parse", "HEAD"],
            phase="git_state",
            timeout=60,
        )
        if code != 0:
            return None
        return output.strip().splitlines()[-1].strip() if output.strip() else None

    def resolve_target(self, target: str, branch: str) -> str:
        candidates = [target]
        if target == branch:
            candidates = [f"origin/{branch}", target]

        for candidate in candidates:
            code, output = self._run_command(
                ["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"],
                phase="git_resolve",
                timeout=60,
            )
            if code == 0 and output.strip():
                return output.strip().splitlines()[-1].strip()

        raise DeployError(
            "target_not_found",
            f"Target commit or branch not found after fetch: {target}",
        )

    def git_checkout_detached(self, target: str) -> None:
        code, _ = self._run_command(
            ["git", "-c", "advice.detachedHead=false", "checkout", "--detach", target],
            phase="git_checkout",
        )
        if code != 0:
            raise DeployError("git_checkout_failed", "git checkout failed")

        code, _ = self._run_command(
            ["git", "reset", "--hard", target],
            phase="git_reset",
        )
        if code != 0:
            raise DeployError("git_reset_failed", "git reset failed")

    def git_checkout(self, target: str) -> None:
        self.git_checkout_detached(target)

    def git_reset(self, target: str) -> None:
        code, _ = self._run_command(
            ["git", "reset", "--hard", target],
            phase="git_reset",
        )
        if code != 0:
            raise DeployError("git_reset_failed", "git reset failed")

    # ------------------------------------------------------------------
    # docker compose
    # ------------------------------------------------------------------
    def docker_compose_config(self, compose_file: str = "docker-compose.yml") -> None:
        code, _ = self._run_command(
            ["docker", "compose", "-f", compose_file, "config", "--quiet"],
            phase="docker_config",
        )
        if code != 0:
            raise DeployError("compose_config_invalid", "docker compose config validation failed")

    def docker_compose_build(self, compose_file: str = "docker-compose.yml") -> None:
        code, _ = self._run_command(
            ["docker", "compose", "-f", compose_file, "build", "--progress", "plain"],
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

    def snapshot_runtime(self, compose_file: str = "docker-compose.yml") -> Dict[str, Any]:
        code, output = self._run_command(
            ["docker", "compose", "-f", compose_file, "ps", "-q"],
            phase="snapshot",
            timeout=60,
        )
        if code != 0:
            logger.warning("failed to snapshot compose containers")
            return {}

        container_ids = [line.strip() for line in output.splitlines() if line.strip()]
        if not container_ids:
            return {}

        code, output = self._run_command(
            [
                "docker",
                "inspect",
                "--format",
                "{{.Name}}\t{{.Config.Image}}\t{{.Image}}\t{{.State.Status}}",
                *container_ids,
            ],
            phase="snapshot",
            timeout=60,
        )
        if code != 0:
            logger.warning("failed to inspect compose containers")
            return {}

        snapshot: Dict[str, Any] = {}
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            name = parts[0].lstrip("/")
            snapshot[name] = {
                "image": parts[1],
                "image_id": parts[2],
                "status": parts[3],
            }
        return snapshot

    def run_pre_deploy(self, cmd: Optional[str]) -> None:
        if not cmd or not cmd.strip():
            return

        code, _ = self._run_command(
            ["bash", "-lc", cmd],
            phase="pre_deploy",
        )
        if code != 0:
            raise DeployError("pre_deploy_failed", "pre_deploy command failed")

    def run_post_deploy(self, cmd: Optional[str]) -> None:
        if not cmd or not cmd.strip():
            return

        code, _ = self._run_command(
            ["bash", "-lc", cmd],
            phase="post_deploy",
        )
        if code != 0:
            raise DeployError("post_deploy_failed", "post_deploy command failed")

    # ------------------------------------------------------------------
    # deployment
    # ------------------------------------------------------------------
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
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if project_id is not None:
            self.project_id = project_id

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
            previous_commit = self.get_current_commit()
            image_snapshot = self.snapshot_runtime(compose_file)

            self._assert_clean()
            self.git_fetch(env=auth["env"], redact=auth["redact"])

            target = target_commit or branch
            target_sha = self.resolve_target(target, branch)
            self.log_collector.info("git_resolve", f"Resolved {target} -> {target_sha}")

            self.git_checkout_detached(target_sha)
            current_commit = self.get_current_commit()
            if current_commit != target_sha:
                raise DeployError(
                    "git_checkout_mismatch",
                    f"HEAD is {current_commit}, expected {target_sha}",
                )

            self.run_pre_deploy(pre_deploy)

            self.docker_compose_config(compose_file)

            if strategy == "compose-build":
                self.docker_compose_build(compose_file)
            elif strategy == "compose-pull":
                self.docker_compose_pull(compose_file)
            else:
                raise DeployError(
                    "invalid_deploy_strategy",
                    f"Unsupported deploy strategy: {strategy}",
                )

            self.docker_compose_up(compose_file)
            self.run_post_deploy(post_deploy)

            return {
                "commit": current_commit,
                "previous_commit": previous_commit,
                "image_snapshot": image_snapshot,
                "target": target,
            }
        finally:
            self._cleanup_git_auth(auth["cleanup_paths"])
