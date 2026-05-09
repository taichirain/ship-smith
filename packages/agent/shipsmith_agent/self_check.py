import logging
import os
import subprocess
import time
from typing import List, Dict, Any, Optional

from .config import get_settings
from . import __version__ as AGENT_VERSION

logger = logging.getLogger(__name__)


class CheckResult:
    def __init__(
        self,
        name: str,
        category: str,
        passed: bool,
        message: str,
        severity: str = "error",
        details: Optional[str] = None,
        resolution: Optional[str] = None,
    ):
        self.name = name
        self.category = category
        self.passed = passed
        self.message = message
        self.severity = severity
        self.details = details
        self.resolution = resolution

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
            "resolution": self.resolution,
        }


RESOLUTIONS = {
    "git_not_installed": "安装 git: apt-get install git 或 yum install git",
    "docker_not_installed": "安装 Docker: https://docs.docker.com/get-docker/",
    "docker_daemon_not_running": "启动 Docker 守护进程: systemctl start docker\n或确保用户在 docker 组中: usermod -aG docker $USER",
    "docker_compose_not_available": "安装 Docker Compose plugin: https://docs.docker.com/compose/install/linux/",
    "workdir_not_configured": "设置 SHIPSMITH_WORKDIR 环境变量，指向部署工作目录",
    "workdir_not_exists": "创建工作目录: mkdir -p /path/to/workdir",
    "workdir_not_writable": "检查目录权限: chmod 755 /path/to/workdir\n或更改所有者: chown $USER:$USER /path/to/workdir",
    "agent_token_not_configured": "设置 SHIPSMITH_AGENT_TOKEN 环境变量",
    "core_url_not_configured": "设置 SHIPSMITH_CORE_URL 环境变量",
    "core_api_unreachable": "检查网络连接和防火墙设置\n确保 SHIPSMITH_CORE_URL 地址正确",
    "core_api_auth_failed": "验证 Agent Token 是否有效\n可在项目页面重新生成 Token",
    "system_resources_low": "清理磁盘空间或扩展系统资源",
}


def _check_command_available(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _check_directory_writable(path: str) -> CheckResult:
    if not os.path.exists(path):
        return CheckResult(
            name="workdir_exists",
            category="filesystem",
            passed=False,
            message=f"工作目录不存在: {path}",
            severity="error",
            details="部署工作目录必须存在才能执行部署操作",
            resolution=RESOLUTIONS["workdir_not_exists"],
        )
    if not os.path.isdir(path):
        return CheckResult(
            name="workdir_is_dir",
            category="filesystem",
            passed=False,
            message=f"路径不是目录: {path}",
            severity="error",
            details="SHIPSMITH_WORKDIR 必须指向一个目录",
            resolution=RESOLUTIONS["workdir_not_exists"],
        )

    try:
        test_file = os.path.join(path, ".shipsmith_test_write")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)

        return CheckResult(
            name="workdir_writable",
            category="filesystem",
            passed=True,
            message=f"工作目录可写: {path}",
            severity="info",
        )
    except PermissionError:
        return CheckResult(
            name="workdir_writable",
            category="filesystem",
            passed=False,
            message=f"权限不足: 无法写入 {path}",
            severity="error",
            details="Agent 需要对工作目录有读写权限才能执行 Git 操作和构建",
            resolution=RESOLUTIONS["workdir_not_writable"],
        )
    except Exception as e:
        return CheckResult(
            name="workdir_writable",
            category="filesystem",
            passed=False,
            message=f"检查目录失败: {path}",
            severity="error",
            details=str(e),
            resolution=RESOLUTIONS["workdir_not_writable"],
        )


def _check_docker_daemon() -> CheckResult:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return CheckResult(
                name="docker_daemon",
                category="docker",
                passed=True,
                message="Docker 守护进程运行正常",
                severity="info",
            )
        else:
            return CheckResult(
                name="docker_daemon",
                category="docker",
                passed=False,
                message="Docker 守护进程不可访问",
                severity="error",
                details=result.stderr or result.stdout,
                resolution=RESOLUTIONS["docker_daemon_not_running"],
            )
    except FileNotFoundError:
        return CheckResult(
            name="docker_daemon",
            category="docker",
            passed=False,
            message="Docker CLI 未安装",
            severity="error",
            details="docker 命令在 PATH 中找不到",
            resolution=RESOLUTIONS["docker_not_installed"],
        )
    except Exception as e:
        return CheckResult(
            name="docker_daemon",
            category="docker",
            passed=False,
            message="检查 Docker 守护进程失败",
            severity="error",
            details=str(e),
            resolution=RESOLUTIONS["docker_daemon_not_running"],
        )


def _check_docker_compose() -> CheckResult:
    if _check_command_available("docker"):
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return CheckResult(
                    name="docker_compose",
                    category="docker",
                    passed=True,
                    message="Docker Compose plugin 可用 (docker compose)",
                    severity="info",
                )
        except Exception:
            pass

    if _check_command_available("docker-compose"):
        return CheckResult(
            name="docker_compose",
            category="docker",
            passed=True,
            message="Docker Compose 独立命令可用 (docker-compose)",
            severity="info",
        )

    return CheckResult(
        name="docker_compose",
        category="docker",
        passed=False,
        message="Docker Compose 不可用",
        severity="error",
        details="需要 docker compose plugin 或 docker-compose 命令",
        resolution=RESOLUTIONS["docker_compose_not_available"],
    )


def _check_docker_resources() -> List[CheckResult]:
    results: List[CheckResult] = []

    if not _check_command_available("docker"):
        return results

    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            try:
                import json

                data = json.loads(result.stdout)
                layers_size = data.get("LayersSize", 0) if isinstance(data, dict) else 0
                if isinstance(layers_size, int) and layers_size > 50 * 1024 * 1024 * 1024:
                    results.append(
                        CheckResult(
                            name="docker_disk_usage",
                            category="docker",
                            passed=False,
                            message="Docker 磁盘使用量超过 50GB",
                            severity="warning",
                            details=f"当前使用: {layers_size / (1024*1024*1024):.1f}GB",
                            resolution="清理未使用的镜像: docker system prune -a",
                        )
                    )
            except Exception:
                pass
    except Exception:
        pass

    return results


def _check_core_connectivity(core_url: str, agent_token: Optional[str] = None) -> List[CheckResult]:
    results: List[CheckResult] = []

    try:
        import httpx

        with httpx.Client(timeout=10) as client:
            response = client.get(f"{core_url}/health")
            if response.status_code == 200:
                results.append(
                    CheckResult(
                        name="core_connectivity",
                        category="network",
                        passed=True,
                        message="Core API 服务可达",
                        severity="info",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="core_connectivity",
                        category="network",
                        passed=False,
                        message=f"Core API 返回状态码: {response.status_code}",
                        severity="error",
                        details="服务可能不正常运行",
                        resolution=RESOLUTIONS["core_api_unreachable"],
                    )
                )
                return results

            if agent_token:
                response = client.get(
                    f"{core_url}/v1/projects",
                    headers={"Authorization": f"Bearer {agent_token}"},
                )
                if response.status_code == 200:
                    results.append(
                        CheckResult(
                            name="core_auth",
                            category="network",
                            passed=True,
                            message="Agent Token 认证成功",
                            severity="info",
                        )
                    )
                elif response.status_code == 401:
                    results.append(
                        CheckResult(
                            name="core_auth",
                            category="network",
                            passed=False,
                            message="Agent Token 无效或已过期",
                            severity="error",
                            details="请在项目页面重新生成 Token",
                            resolution=RESOLUTIONS["core_api_auth_failed"],
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            name="core_auth",
                            category="network",
                            passed=False,
                            message=f"认证请求失败: HTTP {response.status_code}",
                            severity="warning",
                            details=response.text[:200],
                            resolution=RESOLUTIONS["core_api_auth_failed"],
                        )
                    )

    except Exception as e:
        results.append(
            CheckResult(
                name="core_connectivity",
                category="network",
                passed=False,
                message=f"无法连接到 Core API: {core_url}",
                severity="error",
                details=str(e),
                resolution=RESOLUTIONS["core_api_unreachable"],
            )
        )

    return results


def _check_system_resources() -> List[CheckResult]:
    results: List[CheckResult] = []

    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.5)
        if cpu_percent > 90:
            results.append(
                CheckResult(
                    name="cpu_usage",
                    category="system",
                    passed=False,
                    message=f"CPU 使用率过高: {cpu_percent}%",
                    severity="warning",
                    details="高 CPU 使用率可能影响部署性能",
                    resolution=RESOLUTIONS["system_resources_low"],
                )
            )
        else:
            results.append(
                CheckResult(
                    name="cpu_usage",
                    category="system",
                    passed=True,
                    message=f"CPU 使用率正常: {cpu_percent}%",
                    severity="info",
                )
            )

        memory = psutil.virtual_memory()
        mem_percent = memory.percent
        if mem_percent > 90:
            results.append(
                CheckResult(
                    name="memory_usage",
                    category="system",
                    passed=False,
                    message=f"内存使用率过高: {mem_percent}%",
                    severity="warning",
                    details=f"可用内存: {(memory.available / (1024*1024)):.0f}MB",
                    resolution=RESOLUTIONS["system_resources_low"],
                )
            )
        else:
            results.append(
                CheckResult(
                    name="memory_usage",
                    category="system",
                    passed=True,
                    message=f"内存使用率正常: {mem_percent}%",
                    severity="info",
                )
            )

        disk = psutil.disk_usage("/")
        if disk.percent > 90:
            results.append(
                CheckResult(
                    name="disk_usage",
                    category="system",
                    passed=False,
                    message=f"磁盘使用率过高: {disk.percent}%",
                    severity="warning",
                    details=f"可用空间: {(disk.free / (1024*1024*1024)):.1f}GB",
                    resolution=RESOLUTIONS["system_resources_low"],
                )
            )
        else:
            results.append(
                CheckResult(
                    name="disk_usage",
                    category="system",
                    passed=True,
                    message=f"磁盘使用率正常: {disk.percent}%",
                    severity="info",
                )
            )
    except Exception as e:
        logger.warning(f"Failed to check system resources: {e}")
        results.append(
            CheckResult(
                name="system_resources",
                category="system",
                passed=True,
                message="无法获取系统资源信息（psutil 可能未安装）",
                severity="info",
                details=str(e),
            )
        )

    return results


def _check_configuration() -> List[CheckResult]:
    results: List[CheckResult] = []
    settings = get_settings()

    if not settings.agent_token:
        results.append(
            CheckResult(
                name="agent_token_configured",
                category="configuration",
                passed=False,
                message="SHIPSMITH_AGENT_TOKEN 未配置",
                severity="error",
                details="Agent Token 是连接到 Core API 的必要凭证",
                resolution=RESOLUTIONS["agent_token_not_configured"],
            )
        )
    else:
        results.append(
            CheckResult(
                name="agent_token_configured",
                category="configuration",
                passed=True,
                message="Agent Token 已配置",
                severity="info",
            )
        )

    if not settings.core_url:
        results.append(
            CheckResult(
                name="core_url_configured",
                category="configuration",
                passed=False,
                message="SHIPSMITH_CORE_URL 未配置",
                severity="error",
                details="Core API 地址是必要的配置",
                resolution=RESOLUTIONS["core_url_not_configured"],
            )
        )
    else:
        results.append(
            CheckResult(
                name="core_url_configured",
                category="configuration",
                passed=True,
                message=f"Core URL: {settings.core_url}",
                severity="info",
            )
        )

    if not settings.workdir:
        results.append(
            CheckResult(
                name="workdir_configured",
                category="configuration",
                passed=False,
                message="SHIPSMITH_WORKDIR 未配置",
                severity="error",
                details="工作目录是执行部署的必要配置",
                resolution=RESOLUTIONS["workdir_not_configured"],
            )
        )
    else:
        results.append(
            CheckResult(
                name="workdir_configured",
                category="configuration",
                passed=True,
                message=f"工作目录: {settings.workdir}",
                severity="info",
            )
        )

    return results


def run_precheck(
    include_system_resources: bool = True,
    include_docker_resources: bool = True,
) -> Dict[str, Any]:
    settings = get_settings()
    results: List[CheckResult] = []

    results.extend(_check_configuration())

    git_available = _check_command_available("git")
    if git_available:
        results.append(
            CheckResult(
                name="git_available",
                category="tools",
                passed=True,
                message="Git CLI 可用",
                severity="info",
            )
        )
    else:
        results.append(
            CheckResult(
                name="git_available",
                category="tools",
                passed=False,
                message="Git CLI 未安装或不在 PATH 中",
                severity="error",
                details="需要 Git 来拉取代码仓库",
                resolution=RESOLUTIONS["git_not_installed"],
            )
        )

    docker_available = _check_command_available("docker")
    if docker_available:
        results.append(
            CheckResult(
                name="docker_available",
                category="tools",
                passed=True,
                message="Docker CLI 可用",
                severity="info",
            )
        )
        results.append(_check_docker_daemon())
        results.append(_check_docker_compose())
        if include_docker_resources:
            results.extend(_check_docker_resources())
    else:
        results.append(
            CheckResult(
                name="docker_available",
                category="tools",
                passed=False,
                message="Docker CLI 未安装或不在 PATH 中",
                severity="error",
                details="需要 Docker 来运行容器",
                resolution=RESOLUTIONS["docker_not_installed"],
            )
        )

    if settings.workdir and os.path.exists(settings.workdir):
        results.append(_check_directory_writable(settings.workdir))

    if settings.core_url:
        results.extend(_check_core_connectivity(settings.core_url, settings.agent_token))

    if include_system_resources:
        results.extend(_check_system_resources())

    passed_count = sum(1 for r in results if r.passed)
    error_count = sum(1 for r in results if not r.passed and r.severity == "error")
    warning_count = sum(1 for r in results if not r.passed and r.severity == "warning")

    overall_status = "healthy"
    if error_count > 0:
        overall_status = "unhealthy"
    elif warning_count > 0:
        overall_status = "degraded"

    categories = {}
    for r in results:
        if r.category not in categories:
            categories[r.category] = {"passed": 0, "failed": 0, "checks": []}
        categories[r.category]["checks"].append(r.to_dict())
        if r.passed:
            categories[r.category]["passed"] += 1
        else:
            categories[r.category]["failed"] += 1

    return {
        "agent_version": AGENT_VERSION,
        "timestamp": time.time(),
        "overall_status": overall_status,
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "errors": error_count,
            "warnings": warning_count,
        },
        "categories": {k: v for k, v in categories.items()},
        "checks": [r.to_dict() for r in results],
    }
