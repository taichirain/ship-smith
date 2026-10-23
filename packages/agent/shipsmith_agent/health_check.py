import logging
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

    def get_container_statuses(self) -> list:
        containers = []
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            containers.append({
                                "service": parts[0],
                                "status": parts[1],
                                "image": parts[2] if len(parts) > 2 else None,
                                "ports": parts[3].split(", ") if len(parts) > 3 and parts[3] else [],
                            })
        except Exception as e:
            logger.warning(f"Failed to get container statuses: {e}")

        return containers

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
