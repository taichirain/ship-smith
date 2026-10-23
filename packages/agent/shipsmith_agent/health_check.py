import logging
import json
import os
import platform
import shutil
import subprocess
import time
from typing import Optional, Dict, Any

import httpx
import psutil

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self):
        pass

    def get_runtime_info(self) -> Dict[str, Any]:
        shell = os.environ.get("SHELL") or os.environ.get("COMSPEC")
        compose_command = None

        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                compose_command = "docker compose"
        except Exception:
            pass

        if compose_command is None and shutil.which("docker-compose"):
            compose_command = "docker-compose"

        return {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "os_version": platform.version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "shell": shell,
            "path_separator": os.sep,
            "docker_compose_command": compose_command,
        }

    def get_system_metrics(self) -> Dict[str, Any]:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": round(cpu_percent, 1),
            "mem_used_mb": int(memory.used / (1024 * 1024)),
            "mem_total_mb": int(memory.total / (1024 * 1024)),
            "disk_used_percent": round(disk.percent, 1),
        }

    def get_container_statuses(
        self,
        workdir: Optional[str],
        compose_file: Optional[str],
        compose_profiles: Optional[list[str]] = None,
    ) -> list:
        """Return only containers managed by this project's Compose deployment."""
        if not workdir or not compose_file:
            return []

        compose_path = os.path.join(workdir, compose_file)
        if not os.path.isfile(compose_path):
            return []
        expected_compose_path = os.path.realpath(compose_path)

        command = ["docker", "compose"]
        for profile in compose_profiles or []:
            command.extend(["--profile", profile])
        command.extend(["-f", compose_file, "ps", "--all", "--orphans=false", "--format", "json"])

        try:
            result = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                logger.warning("Failed to get project Compose containers: %s", result.stderr.strip())
                return []

            output = result.stdout.strip()
            if not output:
                return []
            try:
                rows = json.loads(output)
            except json.JSONDecodeError:
                # Compose versions may emit one JSON object per line.
                rows = [json.loads(line) for line in output.splitlines() if line.strip()]
            if isinstance(rows, dict):
                rows = [rows]

            containers = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                labels = row.get("Labels") or ""
                if isinstance(labels, str) and "com.docker.compose.oneoff=true" in labels.lower():
                    continue
                config_label = None
                if isinstance(labels, str):
                    config_label = next((
                        item.partition("=")[2]
                        for item in labels.split(",")
                        if item.startswith("com.docker.compose.project.config_files=")
                    ), None)
                elif isinstance(labels, dict):
                    config_label = labels.get("com.docker.compose.project.config_files")
                    if str(labels.get("com.docker.compose.oneoff", "")).lower() == "true":
                        continue
                if not config_label or os.path.realpath(config_label) != expected_compose_path:
                    continue
                ports = row.get("Ports") or ""
                containers.append({
                    "service": row.get("Name") or row.get("Names") or row.get("Service"),
                    "status": row.get("State") or "unknown",
                    "image": row.get("Image"),
                    "ports": [port.strip() for port in ports.split(",") if port.strip()],
                })
            return containers
        except (OSError, subprocess.SubprocessError, ValueError, TypeError) as exc:
            logger.warning("Failed to get project Compose containers: %s", exc)
            return []

    def check_http_health(
        self,
        url: str,
        timeout: int = 10,
        expected_status: int = 200,
    ) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=timeout) as client:
                start = time.time()
                response = client.get(url)
                elapsed_ms = int((time.time() - start) * 1000)

                status = "healthy" if response.status_code == expected_status else "unhealthy"

                return {
                    "status": status,
                    "response_ms": elapsed_ms,
                    "http_status": response.status_code,
                    "expected_status": expected_status,
                }
        except Exception as e:
            logger.warning(f"Health check failed for {url}: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def wait_http_health(
        self,
        url: str,
        timeout: int = 10,
        expected_status: int = 200,
        interval: float = 1.0,
    ) -> Dict[str, Any]:
        """Wait for a newly started service to become ready within one deadline."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.1, deadline - time.monotonic())
            result = self.check_http_health(
                url,
                timeout=min(3.0, remaining),
                expected_status=expected_status,
            )
            if result.get("status") == "healthy":
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return result
            time.sleep(min(interval, remaining))

    def check_tcp_health(self, host: str, port: int, timeout: int = 10) -> Dict[str, Any]:
        import socket

        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            elapsed_ms = int((time.time() - start) * 1000)
            sock.close()

            status = "healthy" if result == 0 else "unhealthy"

            return {
                "status": status,
                "response_ms": elapsed_ms,
            }
        except Exception as e:
            logger.warning(f"TCP health check failed for {host}:{port}: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
            }
