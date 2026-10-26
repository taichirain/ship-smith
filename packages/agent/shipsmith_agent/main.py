import logging
import json
import os
import signal
import sys
import threading
import time
from typing import Optional, Dict, Any

from .config import get_settings
from .client import CoreClient
from .log_collector import LogCollector
from .deployer import Deployer, DeployError
from .outbox import Outbox
from .health_check import HealthChecker, derive_container_health
from .self_check import run_precheck
from . import __version__ as AGENT_VERSION


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TASK_HEARTBEAT_INTERVAL_SECONDS = 60

_ERROR_PHASE_MAP = {
    "git_clone_failed": "git_clone",
    "git_fetch_failed": "git_fetch",
    "target_not_found": "git_resolve",
    "git_checkout_failed": "git_checkout",
    "git_checkout_mismatch": "git_checkout",
    "git_reset_failed": "git_reset",
    "git_remote_missing": "preflight",
    "git_remote_mismatch": "preflight",
    "workdir_not_managed": "preflight",
    "workdir_marker_invalid": "preflight",
    "workdir_project_mismatch": "preflight",
    "workdir_repo_mismatch": "preflight",
    "workdir_dirty": "preflight",
    "workdir_not_empty": "preflight",
    "workdir_missing": "preflight",
    "workdir_not_absolute": "preflight",
    "workdir_forbidden": "preflight",
    "compose_config_invalid": "docker_config",
    "docker_build_failed": "docker_build",
    "docker_pull_failed": "docker_pull",
    "docker_up_failed": "docker_up",
    "pre_deploy_failed": "pre_deploy",
    "post_deploy_failed": "post_deploy",
    "migration_failed": "migration",
    "docker_stop_failed": "service_stop",
    "migration_service_missing": "preflight",
    "migration_command_invalid": "migration",
    "deploy_locked": "preflight",
    "invalid_deploy_strategy": "preflight",
}


def _failure_phase(error_code: str, fallback: str) -> str:
    return _ERROR_PHASE_MAP.get(error_code, fallback)


class Agent:
    def __init__(self):
        self.settings = get_settings()
        self.client = CoreClient(self.settings)
        self.health_checker = HealthChecker()
        self._running = False
        self._task_lock = threading.Lock()
        self._current_task_id: Optional[int] = None
        self._task_heartbeat_thread: Optional[threading.Thread] = None
        self._task_running = False
        self._project_config: Optional[Dict[str, Any]] = None
        self._project_config_updated_at = 0.0
        self._health_lock = threading.Lock()
        self._intentionally_stopped = False
        try:
            self.outbox = Outbox(self.settings.workdir) if self.settings.workdir else None
        except Exception:
            logger.exception("failed to initialize the outbox; results/logs will not be buffered")
            self.outbox = None

        if not self.settings.agent_token:
            raise ValueError("SHIPSMITH_AGENT_TOKEN environment variable is required")

    def stop(self, signum, frame):
        logger.info("Shutdown signal received, stopping agent...")
        self._running = False
        self._task_running = False

    def _task_heartbeat_loop(self, task_id: int):
        logger.debug(f"Starting task heartbeat loop for task {task_id}")
        while self._task_running:
            time.sleep(TASK_HEARTBEAT_INTERVAL_SECONDS)
            if self._task_running:
                logger.debug(f"Sending task heartbeat for task {task_id}")
                self.client.send_task_heartbeat(task_id)
        logger.debug(f"Task heartbeat loop stopped for task {task_id}")

    def _send_logs(self, task_id: int, seq: int, phase: str, content: str) -> bool:
        if self.client.send_logs(task_id, seq, phase, content):
            return True
        if self.outbox is not None:
            self.outbox.enqueue_log(task_id, seq, phase, content)
        return False

    def _finish_task(self, task_id: int, **payload) -> bool:
        if self.outbox is not None:
            self.outbox.enqueue_result(task_id, payload)
        if self.client.finish_task(task_id, **payload):
            if self.outbox is not None:
                self.outbox.remove_result(task_id)
            return True
        return False

    def _flush_outbox(self) -> None:
        if self.outbox is None:
            return

        for path, item in self.outbox.pending_results():
            task_id = item.get("task_id")
            payload = item.get("payload") or {}
            if task_id is not None and self.client.finish_task(task_id, **payload):
                self.outbox.remove(path)

        for path, item in self.outbox.pending_logs():
            task_id = item.get("task_id")
            if task_id is None:
                continue
            if self.client.send_logs(
                task_id,
                item.get("seq", 0),
                item.get("phase"),
                item.get("content", ""),
            ):
                self.outbox.remove(path)

    def _refresh_project_config(self) -> None:
        result = self.client.get_agent_config()
        if result:
            self._project_config = result
            self._project_config_updated_at = time.time()
            self._intentionally_stopped = bool(result.get("intentionally_stopped"))

    def _collect_and_send_heartbeat(self):
        config = self._project_config or {}
        system_metrics = self.health_checker.get_system_metrics()
        configured_workdir = config.get("deploy_workdir")
        if configured_workdir and os.path.realpath(configured_workdir) != os.path.realpath(self.settings.workdir or ""):
            logger.warning("Agent workdir differs from project configuration; skipping container snapshot")
            containers = []
        else:
            containers = self.health_checker.get_container_statuses(
                workdir=self.settings.workdir,
                compose_file=config.get("compose_file"),
                compose_profiles=config.get("compose_profiles"),
            )
        runtime = self.health_checker.get_runtime_info()

        app_health: Dict[str, Any] = {"status": "unknown"}
        if self._task_running:
            app_health = {"status": "unknown", "reason": "deployment_in_progress"}
        elif self._intentionally_stopped or config.get("intentionally_stopped"):
            app_health = {"status": "stopped"}
        else:
            health_url = config.get("healthcheck_url")
            if health_url:
                with self._health_lock:
                    app_health = self.health_checker.check_http_health(
                        health_url,
                        timeout=config.get("healthcheck_timeout_seconds", 10),
                        expected_status=config.get("healthcheck_expected_status", 200),
                    )
            else:
                # No HTTP healthcheck configured: fall back to the container
                # state so an internal-only service is not permanently unknown.
                app_health = {
                    "status": derive_container_health(containers),
                    "source": "containers",
                }

        previous_health = getattr(self, "_last_health_status", None)
        current_health = app_health.get("status")
        self._last_health_status = current_health
        if previous_health == "healthy" and current_health in ("unhealthy", "degraded"):
            threading.Thread(
                target=self._capture_health_diagnostics,
                args=(current_health,),
                daemon=True,
            ).start()

        payload = {
            "agent_version": AGENT_VERSION,
            "system": system_metrics,
            "runtime": runtime,
            "containers": containers,
            "app_health": app_health,
        }

        self.client.send_heartbeat(payload)

    def _sync_flags(self, current_version: int) -> int:
        result = self.client.sync_flags(current_version)
        if result and result.get("changed") and result.get("flags") is not None:
            flags_file = result.get("flags_file_path") or (
                self.settings.workdir + "/flags.json" if self.settings.workdir else "./flags.json"
            )
            try:
                flags_dir = os.path.dirname(flags_file)
                if flags_dir:
                    os.makedirs(flags_dir, exist_ok=True)
                tmp_file = flags_file + ".tmp"
                with open(tmp_file, "w") as f:
                    json.dump(result["flags"], f, indent=2)
                os.replace(tmp_file, flags_file)
                logger.info(f"Flags synced (version {result['version']})")
                return result["version"]
            except Exception as e:
                logger.error(f"Failed to write flags file: {e}")
        return current_version

    def _execute_precheck(self, task_id: int, project_id: int):
        logger.info(f"Running environment precheck for task {task_id}")

        if not self.client.start_task(task_id):
            logger.error(f"Failed to start task {task_id}")
            return

        try:
            precheck_result = run_precheck(
                include_system_resources=True,
                include_docker_resources=True,
            )

            logger.info(f"Precheck completed with status: {precheck_result['overall_status']}")

            self._finish_task(
                task_id=task_id,
                status="success",
                error_code=None,
                error_message=None,
            )

            try:
                import httpx

                with httpx.Client(
                    headers={
                        "Authorization": f"Bearer {self.settings.agent_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                ) as http_client:
                    response = http_client.post(
                        f"{self.settings.core_url.rstrip('/')}/agents/prechecks/result",
                        json={
                            "deployment_id": task_id,
                            "project_id": project_id,
                            "agent_id": self.settings.agent_id if hasattr(self.settings, "agent_id") else "unknown",
                            "precheck_result": precheck_result,
                        },
                    )
                    if response.status_code != 200:
                        logger.warning(f"Failed to save precheck result: HTTP {response.status_code}")
            except Exception as e:
                logger.warning(f"Failed to save precheck result: {e}")

        except Exception as e:
            logger.error(f"Precheck task {task_id} failed: {e}")
            self._finish_task(
                task_id=task_id,
                status="failed",
                error_code="precheck_failed",
                error_message=str(e),
                failure_phase="precheck",
            )

    def _diagnostics_deployer(self, task_or_config, project_id=None):
        quiet = LogCollector(lambda *args, **kwargs: True)
        return Deployer(
            self.settings.workdir,
            quiet,
            project_id=project_id,
            compose_profiles=(task_or_config or {}).get("compose_profiles") or [],
        )

    def _diagnostics_services(self, deployer, config):
        return deployer.resolve_services(
            config.get("service_scope", "app"),
            config.get("app_services"),
            config.get("compose_service") or "app",
        )

    def _execute_diagnostics(self, task_id: int, task: dict, deployer=None) -> None:
        logger.info(f"Collecting diagnostics for task {task_id}")
        if not self.client.start_task(task_id):
            logger.error(f"Failed to start task {task_id}")
            return

        try:
            deployer = deployer or self._diagnostics_deployer(task, task.get("project_id"))
            services = self._diagnostics_services(deployer, task)
            snapshot = deployer.collect_diagnostics(
                task.get("compose_file") or "docker-compose.yml",
                services,
            )
            delivered = self.client.send_diagnostics(
                {
                    "deployment_id": task_id,
                    "trigger": "manual",
                    "reason": "requested from the panel",
                    "content": snapshot["content"],
                    "truncated": snapshot["truncated"],
                }
            )
            self._finish_task(
                task_id=task_id,
                status="success" if delivered else "failed",
                error_code=None if delivered else "diagnostics_upload_failed",
                error_message=None if delivered else "Diagnostics were captured but not delivered",
                failure_phase=None if delivered else "diagnostics",
            )
        except DeployError as e:
            logger.error(f"Diagnostics failed: {e.message}")
            self._finish_task(
                task_id=task_id,
                status="failed",
                error_code=e.error_code,
                error_message=e.message,
                failure_phase="diagnostics",
            )
        except Exception as e:
            logger.error(f"Diagnostics failed with unexpected error: {e}")
            self._finish_task(
                task_id=task_id,
                status="failed",
                error_code="diagnostics_failed",
                error_message=str(e),
                failure_phase="diagnostics",
            )

    def _capture_deploy_failure_diagnostics(self, deployer, compose_file, task, reason):
        """Grab container logs while the failed container still exists."""
        try:
            services = self._diagnostics_services(deployer, task)
            snapshot = deployer.collect_diagnostics(compose_file, services)
            self.client.send_diagnostics(
                {
                    "deployment_id": task.get("id"),
                    "trigger": "deploy_failed",
                    "reason": reason[:200],
                    "content": snapshot["content"],
                    "truncated": snapshot["truncated"],
                }
            )
        except Exception as exc:
            logger.warning(f"Failed to capture post-deploy diagnostics: {exc}")

    def _capture_health_diagnostics(self, status: str) -> None:
        try:
            config = self._project_config or {}
            deployer = self._diagnostics_deployer(config)
            services = self._diagnostics_services(deployer, config)
            snapshot = deployer.collect_diagnostics(
                config.get("compose_file") or "docker-compose.yml",
                services,
            )
            self.client.send_diagnostics(
                {
                    "deployment_id": None,
                    "trigger": "unhealthy",
                    "reason": f"health changed to {status}"[:200],
                    "content": snapshot["content"],
                    "truncated": snapshot["truncated"],
                }
            )
        except Exception as exc:
            logger.warning(f"Failed to capture health diagnostics: {exc}")

    def _execute_service_operation(self, task_id, project_id, kind, task, deployer, log_collector):
        current_phase = "service_stop" if kind == "service_stop" else "service_start"
        compose_file = task.get("compose_file", "docker-compose.yml")
        healthcheck_url = task.get("healthcheck_url")
        service_scope = task.get("service_scope", "app")

        try:
            deployer.assert_managed_repo(task.get("git_repo"))
            requested_services = [s for s in (task.get("services") or []) if s]
            partial = bool(requested_services)
            if partial:
                target_services = requested_services
            else:
                target_services = deployer.resolve_services(
                    service_scope,
                    task.get("app_services"),
                    task.get("compose_service") or "app",
                )

            if kind == "service_stop":
                log_collector.info(
                    "service_stop",
                    f"Stopping services (scope={service_scope}, services={target_services or 'all'}); containers and volumes are preserved...",
                )
                deployer.docker_compose_stop(compose_file, services=target_services)
                if not partial:
                    self._intentionally_stopped = True
                    if isinstance(self._project_config, dict):
                        self._project_config["intentionally_stopped"] = True
                self._collect_and_send_heartbeat()
                self._finish_task(task_id=task_id, status="success")
                return

            log_collector.info(
                "service_start",
                f"Starting services (scope={service_scope}, services={target_services or 'all'})...",
            )
            deployer.docker_compose_up(compose_file, services=target_services)

            health_result: Dict[str, Any] = {"status": "unknown"}
            if healthcheck_url and partial:
                log_collector.info(
                    "health_check",
                    "Partial start: skipping the project-level HTTP health check.",
                )
            elif healthcheck_url:
                current_phase = "health_check"
                log_collector.info("health_check", "Running health check...")
                health_result = self.health_checker.wait_http_health(
                    healthcheck_url,
                    timeout=task.get("healthcheck_timeout_seconds", 10),
                    expected_status=task.get("healthcheck_expected_status", 200),
                )
                if health_result.get("status") != "healthy":
                    log_collector.error("health_check", f"Health check failed: {health_result}")
                    self._finish_task(
                        task_id=task_id,
                        status="failed",
                        error_code="health_check_failed",
                        error_message=f"Health check failed: {health_result}",
                        failure_phase="health_check",
                        health_result=health_result,
                    )
                    return

            if not partial:
                self._intentionally_stopped = False
                if isinstance(self._project_config, dict):
                    self._project_config["intentionally_stopped"] = False
            self._collect_and_send_heartbeat()
            self._finish_task(task_id=task_id, status="success", health_result=health_result)

        except DeployError as e:
            logger.error(f"Task {task_id} failed: {e.message}")
            self._finish_task(
                task_id=task_id,
                status="failed",
                error_code=e.error_code,
                error_message=e.message,
                failure_phase=_failure_phase(e.error_code, current_phase),
            )
        except Exception as e:
            logger.error(f"Task {task_id} failed with unexpected error: {e}")
            self._finish_task(
                task_id=task_id,
                status="failed",
                error_code="unknown_error",
                error_message=str(e),
                failure_phase=current_phase,
            )

    def _execute_task(self, task: dict):
        task_id = task.get("id")
        project_id = task.get("project_id")
        kind = task.get("kind", "deploy")

        logger.info(f"Executing task: id={task_id}, kind={kind}")

        self._task_running = True
        self._current_task_id = task_id
        self._task_lock.acquire()

        try:
            if kind == "precheck":
                self._execute_precheck(task_id, project_id)
                return

            if not self.settings.workdir:
                raise ValueError("SHIPSMITH_WORKDIR environment variable is required for deployment")

            if kind == "logs":
                self._execute_diagnostics(task_id, task)
                return

            commit_hash = task.get("commit_hash")
            deploy_strategy = task.get("deploy_strategy", "compose-build")
            healthcheck_url = task.get("healthcheck_url")
            healthcheck_timeout = task.get("healthcheck_timeout_seconds", 10)
            healthcheck_expected_status = task.get("healthcheck_expected_status", 200)
            migration_service = task.get("migration_service")
            migration_command = task.get("migration_command")
            migration_timeout = task.get("migration_timeout_seconds", 600)
            migration_no_deps = task.get("migration_no_deps", True)
            compose_profiles = task.get("compose_profiles") or []
            build_timeout_seconds = task.get("build_timeout_seconds", 1800)
            pull_timeout_seconds = task.get("pull_timeout_seconds", 900)
            build_no_cache = task.get("build_no_cache", False)

            current_phase = "setup"
            actual_commit = None
            previous_commit = None
            image_snapshot: Dict[str, Any] = {}
            health_result: Dict[str, Any] = {"status": "unknown"}

            self._task_heartbeat_thread = threading.Thread(
                target=self._task_heartbeat_loop,
                args=(task_id,),
                daemon=True,
            )
            self._task_heartbeat_thread.start()

            def send_logs(seq: int, phase: str, content: str) -> bool:
                return self._send_logs(task_id, seq, phase, content)

            log_collector = LogCollector(send_logs)
            deployer = Deployer(
                self.settings.workdir,
                log_collector,
                project_id=project_id,
                compose_profiles=compose_profiles,
            )

            if not self.client.start_task(task_id):
                logger.error(f"Failed to start task {task_id}")
                return

            if kind in ("service_stop", "service_start"):
                self._execute_service_operation(
                    task_id=task_id,
                    project_id=project_id,
                    kind=kind,
                    task=task,
                    deployer=deployer,
                    log_collector=log_collector,
                )
                return

            try:
                git_branch = task.get("git_branch", "main")
                git_repo = task.get("git_repo")
                compose_file = task.get("compose_file", "docker-compose.yml")
                git_credential_type = task.get("git_credential_type", "none")
                git_credential_username = task.get("git_credential_username")
                git_credential_token = task.get("git_credential_token")
                git_credential_ssh_private_key = task.get("git_credential_ssh_private_key")
                git_credential_ssh_known_hosts = task.get("git_credential_ssh_known_hosts")
                pre_deploy = task.get("pre_deploy_command")
                post_deploy = task.get("post_deploy_command")

                current_phase = "git_fetch"
                deploy_result = deployer.deploy(
                    git_repo=git_repo,
                    target_commit=commit_hash,
                    branch=git_branch,
                    strategy=deploy_strategy,
                    git_credential_type=git_credential_type,
                    git_credential_username=git_credential_username,
                    git_credential_token=git_credential_token,
                    git_credential_ssh_private_key=git_credential_ssh_private_key,
                    git_credential_ssh_known_hosts=git_credential_ssh_known_hosts,
                    compose_file=compose_file,
                    pre_deploy=pre_deploy,
                    post_deploy=post_deploy,
                    project_id=project_id,
                    compose_profiles=compose_profiles,
                    migration_service=migration_service,
                    migration_command=migration_command,
                    migration_timeout_seconds=migration_timeout,
                    migration_no_deps=migration_no_deps,
                    build_timeout_seconds=build_timeout_seconds,
                    pull_timeout_seconds=pull_timeout_seconds,
                    build_no_cache=build_no_cache,
                    service_scope=task.get("service_scope", "app"),
                    app_services=task.get("app_services"),
                    compose_service=task.get("compose_service") or "app",
                    deploy_services=task.get("services"),
                    release_tag_env=(
                        task.get("release_tag_env")
                        or (self._project_config or {}).get("release_tag_env")
                        or None
                    ),
                )
                actual_commit = deploy_result.get("commit")
                previous_commit = deploy_result.get("previous_commit")
                image_snapshot = deploy_result.get("image_snapshot") or {}

                final_status = "success" if kind == "deploy" else "rolled_back"

                current_phase = "health_check"
                log_collector.info("health_check", "Running health check...")

                if healthcheck_url:
                    health_result = self.health_checker.wait_http_health(
                        healthcheck_url,
                        timeout=healthcheck_timeout,
                        expected_status=healthcheck_expected_status,
                    )
                    logger.info(f"Health check result: {health_result}")
                    
                    if health_result.get("status") != "healthy":
                        logger.warning(f"Health check failed for task {task_id}")
                        final_status = "failed" if kind == "deploy" else "rollback_failed"
                        error_msg = f"Health check failed: {health_result}"
                        log_collector.error("health_check", error_msg)
                        self._capture_deploy_failure_diagnostics(deployer, compose_file, task, error_msg)
                        self._finish_task(
                            task_id=task_id,
                            status=final_status,
                            commit_hash=actual_commit,
                            target_commit_hash=actual_commit,
                            previous_commit_hash=previous_commit,
                            image_snapshot=image_snapshot,
                            health_result=health_result,
                            error_code="health_check_failed",
                            error_message=error_msg,
                            failure_phase="health_check",
                        )
                        logger.info(f"Task {task_id} completed with health check failure")
                        return

                self._intentionally_stopped = False
                if isinstance(self._project_config, dict):
                    self._project_config["intentionally_stopped"] = False
                self._collect_and_send_heartbeat()

                self._finish_task(
                    task_id=task_id,
                    status=final_status,
                    commit_hash=actual_commit,
                    target_commit_hash=actual_commit,
                    previous_commit_hash=previous_commit,
                    image_snapshot=image_snapshot,
                    health_result=health_result,
                )
                logger.info(f"Task {task_id} completed: {final_status}")

            except DeployError as e:
                logger.error(f"Task {task_id} failed: {e.message}")
                final_status = "failed" if kind == "deploy" else "rollback_failed"
                self._finish_task(
                    task_id=task_id,
                    status=final_status,
                    commit_hash=actual_commit,
                    target_commit_hash=actual_commit,
                    previous_commit_hash=previous_commit,
                    image_snapshot=image_snapshot,
                    error_code=e.error_code,
                    error_message=e.message,
                    failure_phase=_failure_phase(e.error_code, current_phase),
                )
            except Exception as e:
                logger.error(f"Task {task_id} failed with unexpected error: {e}")
                final_status = "failed" if kind == "deploy" else "rollback_failed"
                self._finish_task(
                    task_id=task_id,
                    status=final_status,
                    commit_hash=actual_commit,
                    target_commit_hash=actual_commit,
                    previous_commit_hash=previous_commit,
                    image_snapshot=image_snapshot,
                    error_code="unknown_error",
                    error_message=str(e),
                    failure_phase=current_phase,
                )

        finally:
            self._task_running = False
            self._current_task_id = None
            if hasattr(self, "_task_heartbeat_thread") and self._task_heartbeat_thread and self._task_heartbeat_thread.is_alive():
                self._task_heartbeat_thread.join(timeout=2)
            self._task_lock.release()

    def run(self):
        logger.info(f"ShipSmith Agent starting (core: {self.settings.core_url})")

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        self._running = True
        last_heartbeat = 0
        last_flags_sync = 0
        last_project_config_refresh = 0
        last_outbox_flush = 0
        flags_version = 0

        self._refresh_project_config()
        last_project_config_refresh = time.time()
        self._flush_outbox()
        self._collect_and_send_heartbeat()

        while self._running:
            try:
                if not self._task_lock.locked():
                    task = self.client.poll_task()
                    if task:
                        t = threading.Thread(
                            target=self._execute_task,
                            args=(task,),
                            daemon=True,
                        )
                        t.start()

                now = time.time()
                if now - last_heartbeat >= self.settings.heartbeat_interval_seconds:
                    self._collect_and_send_heartbeat()
                    last_heartbeat = now

                if now - last_flags_sync >= self.settings.flags_sync_interval_seconds:
                    flags_version = self._sync_flags(flags_version)
                    last_flags_sync = now

                if now - last_project_config_refresh >= self.settings.project_config_refresh_interval_seconds:
                    self._refresh_project_config()
                    last_project_config_refresh = now

                if now - last_outbox_flush >= 10:
                    self._flush_outbox()
                    last_outbox_flush = now

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            time.sleep(1)

        logger.info("Agent stopped")
        self.client.close()


def _format_check_output(result: Dict[str, Any]) -> str:
    status = "[OK]" if result["passed"] else "[FAIL]" if result["severity"] == "error" else "[WARN]"
    lines = [f"{status} {result['name']}"]
    lines.append(f"   {result['message']}")
    if result.get("details"):
        lines.append(f"   Details: {result['details']}")
    if not result["passed"] and result.get("resolution"):
        lines.append(f"   Resolution: {result['resolution']}")
    return "\n".join(lines)


def run_selfcheck(output_json: bool = False, include_system_resources: bool = True, include_docker_resources: bool = True):
    precheck_result = run_precheck(
        include_system_resources=include_system_resources,
        include_docker_resources=include_docker_resources,
    )

    if output_json:
        print(json.dumps(precheck_result, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("ShipSmith Agent 环境预检")
        print("=" * 60)
        print()

        status_map = {
            "healthy": ("✓", "健康 - 所有检查通过"),
            "degraded": ("!", "降级 - 存在警告"),
            "unhealthy": ("✗", "不健康 - 存在错误"),
        }
        status_char, status_desc = status_map.get(
            precheck_result["overall_status"],
            ("?", "未知状态"),
        )
        print(f"{status_char} 整体状态: {status_desc}")
        print(f"  通过: {precheck_result['summary']['passed']}/{precheck_result['summary']['total']}")
        print(f"  错误: {precheck_result['summary']['errors']}, 警告: {precheck_result['summary']['warnings']}")
        print()

        for category_name, category_data in precheck_result["categories"].items():
            category_passed = category_data["passed"]
            category_failed = category_data["failed"]
            category_display = {
                "configuration": "配置检查",
                "tools": "工具检查",
                "docker": "Docker 检查",
                "filesystem": "文件系统检查",
                "network": "网络检查",
                "system": "系统资源检查",
            }.get(category_name, category_name)

            print(f"--- {category_display} ({category_passed}/{category_passed + category_failed}) ---")
            for check in category_data["checks"]:
                print(_format_check_output(check))
                print()

        print("-" * 60)
        if precheck_result["overall_status"] == "healthy":
            print("所有检查通过！Agent 已准备就绪。")
            print("运行 'shipsmith-agent' 启动 Agent。")
        else:
            failed_checks = [c["name"] for c in precheck_result["checks"] if not c["passed"]]
            print(f"发现问题: {', '.join(failed_checks)}")
            print()
            print("请根据上述建议修复问题后重新运行预检。")

    return 0 if precheck_result["overall_status"] == "healthy" else 1


def show_help():
    print("ShipSmith Agent")
    print()
    print("Usage:")
    print("  shipsmith-agent          Start the agent")
    print("  shipsmith-agent selfcheck  Run self-check")
    print("  shipsmith-agent help       Show this help")
    print()
    print("Environment Variables:")
    print("  SHIPSMITH_CORE_URL       Core API URL (default: http://localhost:8000/api/v1)")
    print("  SHIPSMITH_AGENT_TOKEN    Agent authentication token (required)")
    print("  SHIPSMITH_WORKDIR        Working directory for deployments (required)")
    print("  SHIPSMITH_POLL_INTERVAL  Task poll interval in seconds (default: 30)")
    print("  SHIPSMITH_HEARTBEAT_INTERVAL  Heartbeat interval in seconds (default: 30)")
    print("  SHIPSMITH_FLAGS_INTERVAL  Flags sync interval in seconds (default: 30)")
    print("  SHIPSMITH_LOG_LEVEL      Log level (default: INFO)")


def main():
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "selfcheck":
            output_json = "--json" in sys.argv or "-j" in sys.argv
            sys.exit(run_selfcheck(output_json))
        
        elif command == "help" or command == "--help" or command == "-h":
            show_help()
            sys.exit(0)
        
        else:
            print(f"Unknown command: {command}")
            print()
            show_help()
            sys.exit(1)
    
    try:
        agent = Agent()
        agent.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
