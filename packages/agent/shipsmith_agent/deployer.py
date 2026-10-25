import hashlib
import json
import logging
import os
import re
import shlex
import signal
import subprocess
import threading
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

try:
    import fcntl
except ImportError:  # pragma: no cover - the Agent targets Linux
    fcntl = None

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
    "service_stop": 300,
    "service_start": 300,
    "migration": 600,
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
    def __init__(
        self,
        workdir: str,
        log_collector: LogCollector,
        project_id: Optional[int] = None,
        compose_profiles: Optional[List[str]] = None,
    ):
        self.workdir = os.path.abspath(workdir) if workdir else ""
        self.log_collector = log_collector
        self.project_id = project_id
        self.compose_profiles = [str(p) for p in (compose_profiles or []) if str(p).strip()]

    @contextmanager
    def _deploy_lock(self):
        if fcntl is None:
            yield
            return

        lock_dir = Path(tempfile.gettempdir()) / "shipsmith-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(self.workdir.encode("utf-8")).hexdigest()[:16]
        lock_path = lock_dir / f"{key}.lock"
        handle = lock_path.open("w", encoding="utf-8")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DeployError(
                    "deploy_locked",
                    "Another deployment is already running for this workdir",
                )
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            handle.close()

    def _compose_args(self, compose_file: str) -> List[str]:
        args = ["docker", "compose"]
        for profile in self.compose_profiles:
            args.extend(["--profile", profile])
        args.extend(["-f", compose_file])
        return args

    # ------------------------------------------------------------------
    # command execution
    # ------------------------------------------------------------------
    def _redact(self, text: str, secrets: Optional[List[str]] = None) -> str:
        value = text or ""
        for secret in secrets or []:
            if secret:
                value = value.replace(secret, "***")

        value = re.sub(
            r"(?i)([a-z][a-z0-9+.-]*://[^\s/@:]+:)[^@\s]+@",
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
            [*self._compose_args(compose_file), "config", "--quiet"],
            phase="docker_config",
        )
        if code != 0:
            raise DeployError("compose_config_invalid", "docker compose config validation failed")

    def docker_compose_build(
        self,
        compose_file: str = "docker-compose.yml",
        timeout: Optional[int] = None,
        no_cache: bool = False,
        services: Optional[List[str]] = None,
    ) -> None:
        cmd = [*self._compose_args(compose_file), "build", "--progress", "plain"]
        if no_cache:
            cmd.append("--no-cache")
        if services:
            cmd.extend(services)
        code, _ = self._run_command(
            cmd,
            phase="docker_build",
            timeout=timeout,
        )
        if code != 0:
            raise DeployError("docker_build_failed", "docker compose build failed")

    def docker_compose_pull(
        self,
        compose_file: str = "docker-compose.yml",
        timeout: Optional[int] = None,
        services: Optional[List[str]] = None,
    ) -> None:
        cmd = [*self._compose_args(compose_file), "pull"]
        if services:
            cmd.extend(services)
        code, _ = self._run_command(
            cmd,
            phase="docker_pull",
            timeout=timeout,
        )
        if code != 0:
            raise DeployError("docker_pull_failed", "docker compose pull failed")

    def docker_compose_up(
        self,
        compose_file: str = "docker-compose.yml",
        services: Optional[List[str]] = None,
    ) -> None:
        cmd = [*self._compose_args(compose_file), "up", "-d"]
        if services:
            cmd.append("--no-deps")
            cmd.extend(services)
        code, _ = self._run_command(
            cmd,
            phase="docker_up",
        )
        if code != 0:
            raise DeployError("docker_up_failed", "docker compose up failed")

    def assert_managed_repo(self, git_repo: str) -> None:
        """Validate ownership without cloning or touching the worktree."""
        self._assert_workdir_is_safe()
        if not self.project_id:
            raise DeployError("project_id_missing", "Agent task did not include a project id")
        if not (Path(self.workdir) / ".git").exists():
            raise DeployError(
                "workdir_not_managed",
                f"Deploy workdir is not initialized by ShipSmith: {self.workdir}",
            )
        self._validate_marker(git_repo)
        self._assert_remote_matches(git_repo)

    def docker_compose_stop(
        self,
        compose_file: str = "docker-compose.yml",
        services: Optional[List[str]] = None,
    ) -> None:
        cmd = [*self._compose_args(compose_file), "stop"]
        if services:
            cmd.extend(services)
        code, _ = self._run_command(
            cmd,
            phase="service_stop",
        )
        if code != 0:
            raise DeployError("docker_stop_failed", "docker compose stop failed")

    @staticmethod
    def resolve_services(
        service_scope: str,
        app_services: Optional[List[str]],
        compose_service: str,
    ) -> List[str]:
        if service_scope == "all":
            return []
        services = list(app_services or [])
        if service_scope != "app" or not services or compose_service not in services:
            raise DeployError(
                "app_services_invalid",
                "App scope requires an explicit service list containing the primary Compose service",
            )
        return services

    def collect_diagnostics(
        self,
        compose_file: str,
        services: List[str],
        tail: int = 200,
        max_bytes: int = 65536,
    ) -> Dict[str, Any]:
        """Capture container state plus the tail of each service's logs.

        The result is redacted and hard-capped, so a crash loop cannot flood
        the control plane.
        """
        parts: List[str] = []

        _, ps_output = self._run_command(
            [
                *self._compose_args(compose_file),
                "ps",
                "--format",
                "table {{.Service}}\t{{.State}}\t{{.Status}}",
            ],
            phase="diagnostics",
            timeout=60,
        )
        parts.append("== docker compose ps ==")
        parts.append(ps_output.strip() if ps_output.strip() else "(no containers reported)")

        # Share the budget between services so one noisy container cannot
        # consume the whole snapshot.
        per_service = max(2048, max_bytes // max(1, len(services)))
        for service in services:
            _, logs_output = self._run_command(
                [
                    *self._compose_args(compose_file),
                    "logs",
                    "--no-color",
                    "--timestamps",
                    "--tail",
                    str(tail),
                    service,
                ],
                phase="diagnostics",
                timeout=90,
            )
            body = logs_output.rstrip() if logs_output.strip() else "(no log output)"
            encoded_body = body.encode("utf-8")
            if len(encoded_body) > per_service:
                body = encoded_body[:per_service].decode("utf-8", "ignore") + "\n... [service truncated]"
            parts.append("")
            parts.append(f"== logs: {service} (last {tail} lines) ==")
            parts.append(body)

        content = self._redact("\n".join(parts))
        encoded = content.encode("utf-8")
        truncated = len(encoded) > max_bytes
        if truncated:
            content = encoded[:max_bytes].decode("utf-8", "ignore") + "\n... [truncated]"

        return {
            "content": content,
            "byte_size": len(content.encode("utf-8")),
            "truncated": truncated,
        }

    def snapshot_runtime(self, compose_file: str = "docker-compose.yml") -> Dict[str, Any]:
        code, output = self._run_command(
            [*self._compose_args(compose_file), "ps", "-q"],
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

    def run_migration(
        self,
        compose_file: str,
        service: Optional[str],
        command: Optional[str],
        timeout: int = 600,
        no_deps: bool = True,
    ) -> None:
        if not command or not command.strip():
            return
        if not service or not service.strip():
            raise DeployError(
                "migration_service_missing",
                "migration_service is required when migration_command is set",
            )

        try:
            extra_args = shlex.split(command)
        except ValueError as exc:
            raise DeployError(
                "migration_command_invalid",
                f"Invalid migration command: {exc}",
            )
        if not extra_args:
            return

        cmd = self._compose_args(compose_file) + ["run", "--rm"]
        if no_deps:
            cmd.append("--no-deps")
        cmd.extend([service.strip(), *extra_args])

        code, _ = self._run_command(cmd, phase="migration", timeout=timeout)
        if code != 0:
            raise DeployError("migration_failed", "database migration failed")

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
    def deploy(self, *args, **kwargs):
        with self._deploy_lock():
            return self._deploy(*args, **kwargs)

    def _deploy(
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
        compose_profiles: Optional[List[str]] = None,
        migration_service: Optional[str] = None,
        migration_command: Optional[str] = None,
        migration_timeout_seconds: int = 600,
        migration_no_deps: bool = True,
        build_timeout_seconds: int = 1800,
        pull_timeout_seconds: int = 900,
        build_no_cache: bool = False,
        service_scope: str = "all",
        app_services: Optional[List[str]] = None,
        compose_service: str = "app",
    ) -> Dict[str, Any]:
        if project_id is not None:
            self.project_id = project_id
        if compose_profiles is not None:
            self.compose_profiles = [str(p) for p in compose_profiles if str(p).strip()]
        target_services = self.resolve_services(service_scope, app_services, compose_service)

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
                self.docker_compose_build(
                    compose_file,
                    timeout=build_timeout_seconds,
                    no_cache=build_no_cache,
                    services=target_services,
                )
            elif strategy == "compose-pull":
                self.docker_compose_pull(
                    compose_file,
                    timeout=pull_timeout_seconds,
                    services=target_services,
                )
            else:
                raise DeployError(
                    "invalid_deploy_strategy",
                    f"Unsupported deploy strategy: {strategy}",
                )

            self.run_migration(
                compose_file=compose_file,
                service=migration_service,
                command=migration_command,
                timeout=migration_timeout_seconds,
                no_deps=migration_no_deps,
            )

            self.docker_compose_up(compose_file, services=target_services)
            self.run_post_deploy(post_deploy)

            return {
                "commit": current_commit,
                "previous_commit": previous_commit,
                "image_snapshot": image_snapshot,
                "target": target,
            }
        finally:
            self._cleanup_git_auth(auth["cleanup_paths"])
