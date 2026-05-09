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
from .health_check import HealthChecker
from .self_check import run_precheck
from . import __version__ as AGENT_VERSION


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

TASK_HEARTBEAT_INTERVAL_SECONDS = 60


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

    def _collect_and_send_heartbeat(self):
        system_metrics = self.health_checker.get_system_metrics()
        containers = self.health_checker.get_container_statuses()
        runtime = self.health_checker.get_runtime_info()

        payload = {
            "agent_version": AGENT_VERSION,
            "system": system_metrics,
            "runtime": runtime,
            "containers": containers,
            "app_health": {
                "status": "unknown",
            },
        }

        self.client.send_heartbeat(payload)

    def _sync_flags(self, current_version: int) -> int:
        result = self.client.sync_flags(current_version)
        if result and result.get("changed") and result.get("flags") is not None:
            flags_file = self.settings.workdir + "/flags.json" if self.settings.workdir else "./flags.json"
            try:
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

            self.client.finish_task(
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
            self.client.finish_task(
                task_id=task_id,
                status="failed",
                error_code="precheck_failed",
                error_message=str(e),
                failure_phase="precheck",
            )

    def _execute_task(self, task: dict):
        task_id = task.get("id")
        project_id = task.get("project_id")
        kind = task.get("kind", "deploy")

        logger.info(f"Executing task: id={task_id}, kind={kind}")

        self._task_running = True
        self._current_task_id = task_id

        try:
            if kind == "precheck":
                self._execute_precheck(task_id, project_id)
                return

            if not self.settings.workdir:
                raise ValueError("SHIPSMITH_WORKDIR environment variable is required for deployment")

            commit_hash = task.get("commit_hash")
            deploy_strategy = task.get("deploy_strategy", "compose-build")
            healthcheck_url = task.get("healthcheck_url")
            healthcheck_timeout = task.get("healthcheck_timeout_seconds", 10)

            current_phase = "setup"

            self._task_heartbeat_thread = threading.Thread(
                target=self._task_heartbeat_loop,
                args=(task_id,),
                daemon=True,
            )
            self._task_heartbeat_thread.start()

            def send_logs(seq: int, phase: str, content: str) -> bool:
                return self.client.send_logs(task_id, seq, phase, content)

            log_collector = LogCollector(send_logs)
            deployer = Deployer(self.settings.workdir, log_collector)

            if not self.client.start_task(task_id):
                logger.error(f"Failed to start task {task_id}")
                return

            try:
                git_branch = task.get("git_branch", "main")
                compose_file = task.get("compose_file", "docker-compose.yml")

                current_phase = "git_fetch"
                actual_commit = deployer.deploy(
                    target_commit=commit_hash,
                    branch=git_branch,
                    strategy=deploy_strategy,
                    compose_file=compose_file,
                )

                final_status = "success" if kind == "deploy" else "rolled_back"

                current_phase = "health_check"
                log_collector.info("health_check", "Running health check...")

                health_result = {"status": "unknown"}
                if healthcheck_url:
                    health_result = self.health_checker.check_http_health(
                        healthcheck_url,
                        timeout=healthcheck_timeout,
                    )
                    logger.info(f"Health check result: {health_result}")
                    
                    if health_result.get("status") != "healthy":
                        logger.warning(f"Health check failed for task {task_id}")
                        final_status = "failed" if kind == "deploy" else "rollback_failed"
                        error_msg = f"Health check failed: {health_result}"
                        log_collector.error("health_check", error_msg)
                        self.client.finish_task(
                            task_id=task_id,
                            status=final_status,
                            commit_hash=actual_commit,
                            error_code="health_check_failed",
                            error_message=error_msg,
                            failure_phase="health_check",
                        )
                        logger.info(f"Task {task_id} completed with health check failure")
                        return

                self._collect_and_send_heartbeat()

                self.client.finish_task(
                    task_id=task_id,
                    status=final_status,
                    commit_hash=actual_commit,
                )
                logger.info(f"Task {task_id} completed: {final_status}")

            except DeployError as e:
                logger.error(f"Task {task_id} failed: {e.message}")
                final_status = "failed" if kind == "deploy" else "rollback_failed"
                self.client.finish_task(
                    task_id=task_id,
                    status=final_status,
                    error_code=e.error_code,
                    error_message=e.message,
                    failure_phase=current_phase,
                )
            except Exception as e:
                logger.error(f"Task {task_id} failed with unexpected error: {e}")
                final_status = "failed" if kind == "deploy" else "rollback_failed"
                self.client.finish_task(
                    task_id=task_id,
                    status=final_status,
                    error_code="unknown_error",
                    error_message=str(e),
                    failure_phase=current_phase,
                )

        finally:
            self._task_running = False
            self._current_task_id = None
            if hasattr(self, "_task_heartbeat_thread") and self._task_heartbeat_thread and self._task_heartbeat_thread.is_alive():
                self._task_heartbeat_thread.join(timeout=2)

    def run(self):
        logger.info(f"ShipSmith Agent starting (core: {self.settings.core_url})")

        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

        self._running = True
        last_heartbeat = 0
        last_flags_sync = 0
        flags_version = 0

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
