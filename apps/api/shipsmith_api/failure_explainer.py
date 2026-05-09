from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import re


FAILURE_PHASES = {
    "setup": "准备阶段",
    "git_fetch": "拉取代码",
    "git_checkout": "检出代码",
    "git_reset": "重置代码",
    "docker_build": "构建镜像",
    "docker_pull": "拉取镜像",
    "docker_up": "启动容器",
    "pre_deploy": "部署前钩子",
    "post_deploy": "部署后钩子",
    "health_check": "健康检查",
    "rollback": "回滚",
    "precheck": "环境预检",
}


ERROR_CODE_RULES: Dict[str, Dict[str, Any]] = {
    "git_fetch_failed": {
        "title": "拉取代码失败",
        "category": "git",
        "human_explanation": (
            "Agent 无法从远程 Git 仓库拉取代码。这通常是由于网络问题、仓库权限或仓库地址错误导致的。"
        ),
        "checklist": [
            {
                "action": "检查网络连接",
                "command": "ping github.com",
                "description": "确保服务器可以访问 Git 托管平台",
            },
            {
                "action": "验证仓库地址",
                "command": "git remote -v",
                "description": "在部署工作目录中执行，确认仓库地址正确",
            },
            {
                "action": "检查 SSH 密钥权限",
                "command": "ssh -T git@github.com",
                "description": "如果使用 SSH 协议，确认 SSH 密钥已配置并有读取权限",
            },
            {
                "action": "检查 token 有效性",
                "description": "如果使用 HTTPS 协议，确认 access token 或密码未过期",
            },
        ],
        "resolution_steps": [
            "1. 确认服务器可以访问 Git 托管平台（GitHub, GitLab 等）",
            "2. 检查仓库地址是否正确配置",
            "3. 验证 SSH 密钥或 access token 的权限",
            "4. 尝试手动执行 `git fetch` 查看具体错误",
        ],
    },
    "git_checkout_failed": {
        "title": "代码检出失败",
        "category": "git",
        "human_explanation": (
            "Agent 无法检出指定的分支或 commit。这可能是分支不存在、commit 不存在或有未提交的更改导致的。"
        ),
        "checklist": [
            {
                "action": "检查分支是否存在",
                "command": "git branch -a",
                "description": "确认配置的分支在远程仓库中存在",
            },
            {
                "action": "检查工作目录状态",
                "command": "git status",
                "description": "查看是否有未提交的更改导致冲突",
            },
            {
                "action": "手动清理",
                "command": "git reset --hard && git clean -fd",
                "description": "谨慎使用：重置所有本地更改",
            },
        ],
        "resolution_steps": [
            "1. 确认配置的分支名正确",
            "2. 检查工作目录是否有未提交的更改",
            "3. 如有需要，手动清理工作目录",
            "4. 尝试手动执行 `git checkout <branch>` 查看具体错误",
        ],
    },
    "git_reset_failed": {
        "title": "代码重置失败",
        "category": "git",
        "human_explanation": (
            "Agent 无法将代码重置到指定的 commit。这通常发生在目标 commit 不存在或工作目录有冲突时。"
        ),
        "checklist": [
            {
                "action": "确认 commit 存在",
                "command": "git log --oneline -10",
                "description": "查看最近的 commit 历史",
            },
            {
                "action": "检查是否有本地更改",
                "command": "git status",
                "description": "确保没有未提交的更改干扰重置",
            },
        ],
        "resolution_steps": [
            "1. 确认目标 commit hash 正确",
            "2. 检查并清理本地更改",
            "3. 手动执行 `git reset --hard <commit>` 查看具体错误",
        ],
    },
    "docker_build_failed": {
        "title": "Docker 镜像构建失败",
        "category": "docker",
        "human_explanation": (
            "Docker 无法构建镜像。常见原因包括：Dockerfile 语法错误、依赖包无法下载、构建上下文过大等。"
        ),
        "checklist": [
            {
                "action": "检查 Dockerfile",
                "description": "确认 Dockerfile 语法正确，基础镜像存在",
            },
            {
                "action": "检查磁盘空间",
                "command": "df -h",
                "description": "确保有足够的磁盘空间用于构建",
            },
            {
                "action": "检查网络连接",
                "description": "确认可以访问 Docker Hub 和依赖包仓库",
            },
            {
                "action": "手动构建",
                "command": "docker compose build",
                "description": "在部署目录手动执行，查看完整的构建日志",
            },
        ],
        "resolution_steps": [
            "1. 检查 Dockerfile 语法是否正确",
            "2. 确认基础镜像可访问",
            "3. 检查依赖包是否可以正常下载",
            "4. 查看完整的构建日志定位具体错误",
            "5. 清理 Docker 缓存后重试：`docker system prune -f`",
        ],
    },
    "docker_pull_failed": {
        "title": "Docker 镜像拉取失败",
        "category": "docker",
        "human_explanation": (
            "Docker 无法拉取指定的镜像。这可能是镜像不存在、权限不足或网络问题导致的。"
        ),
        "checklist": [
            {
                "action": "检查镜像名称",
                "description": "确认 compose 文件中的镜像名称和标签正确",
            },
            {
                "action": "检查 Docker 登录状态",
                "command": "docker info",
                "description": "如果使用私有镜像仓库，确认已登录",
            },
            {
                "action": "测试网络",
                "command": "docker pull hello-world",
                "description": "测试 Docker 是否可以正常拉取公共镜像",
            },
        ],
        "resolution_steps": [
            "1. 确认镜像名称和标签正确",
            "2. 检查私有仓库的登录状态",
            "3. 测试 Docker 是否可以拉取公共镜像",
            "4. 检查网络连接和防火墙设置",
        ],
    },
    "docker_up_failed": {
        "title": "容器启动失败",
        "category": "docker",
        "human_explanation": (
            "容器无法启动。常见原因包括：配置文件错误、环境变量缺失、端口冲突、卷挂载失败等。"
        ),
        "checklist": [
            {
                "action": "检查端口占用",
                "command": "netstat -tulpn | grep <port>",
                "description": "确认 compose 文件中配置的端口没有被其他进程占用",
            },
            {
                "action": "检查环境变量",
                "description": "确认 .env 文件存在且包含所需的环境变量",
            },
            {
                "action": "检查卷挂载",
                "description": "确认挂载的目录存在且有权限",
            },
            {
                "action": "查看容器日志",
                "command": "docker compose logs",
                "description": "查看容器启动时的具体错误信息",
            },
        ],
        "resolution_steps": [
            "1. 检查 compose 文件配置是否正确",
            "2. 确认环境变量文件存在且有效",
            "3. 检查端口是否被其他进程占用",
            "4. 查看容器日志定位具体错误",
            "5. 手动执行 `docker compose up` 查看完整输出",
        ],
    },
    "pre_deploy_failed": {
        "title": "部署前钩子执行失败",
        "category": "hook",
        "human_explanation": (
            "部署前自定义脚本执行失败。请检查 pre_deploy 命令配置是否正确。"
        ),
        "checklist": [
            {
                "action": "检查脚本路径",
                "description": "确认脚本文件存在且有执行权限",
            },
            {
                "action": "检查脚本内容",
                "description": "确认脚本语法正确，可以独立执行",
            },
        ],
        "resolution_steps": [
            "1. 检查 pre_deploy 命令配置",
            "2. 手动执行脚本查看错误信息",
            "3. 确认脚本有执行权限：`chmod +x <script>`",
        ],
    },
    "post_deploy_failed": {
        "title": "部署后钩子执行失败",
        "category": "hook",
        "human_explanation": (
            "部署后自定义脚本执行失败。容器可能已经启动，但后续操作失败。"
        ),
        "checklist": [
            {
                "action": "检查容器状态",
                "command": "docker compose ps",
                "description": "确认容器是否正常运行",
            },
            {
                "action": "检查脚本",
                "description": "确认 post_deploy 脚本配置正确",
            },
        ],
        "resolution_steps": [
            "1. 确认容器是否正常启动",
            "2. 检查 post_deploy 命令配置",
            "3. 手动执行脚本查看错误",
        ],
    },
    "health_check_failed": {
        "title": "健康检查失败",
        "category": "app",
        "human_explanation": (
            "容器已启动，但健康检查接口返回错误。这可能是应用启动慢、配置错误或应用本身有问题。"
        ),
        "checklist": [
            {
                "action": "检查健康检查配置",
                "description": "确认 healthcheck_url 配置正确",
            },
            {
                "action": "查看应用日志",
                "command": "docker compose logs <service>",
                "description": "查看应用启动日志，确认应用是否正常初始化",
            },
            {
                "action": "测试健康检查",
                "command": "curl -v <healthcheck_url>",
                "description": "从服务器本地测试健康检查接口",
            },
            {
                "action": "检查超时设置",
                "description": "如果应用启动慢，考虑增加 healthcheck_timeout_seconds",
            },
        ],
        "resolution_steps": [
            "1. 确认健康检查 URL 配置正确",
            "2. 查看应用日志，确认应用是否正常启动",
            "3. 本地 curl 测试健康检查接口",
            "4. 如果应用启动慢，增加超时时间",
            "5. 检查容器内应用是否监听正确的端口",
        ],
    },
    "precheck_failed": {
        "title": "环境预检失败",
        "category": "system",
        "human_explanation": (
            "Agent 环境预检失败。请查看预检结果详情，了解具体是哪些检查项不通过。"
        ),
        "checklist": [
            {
                "action": "查看预检结果",
                "description": "在项目详情页查看 Agent 环境预检的详细结果",
            },
        ],
        "resolution_steps": [
            "1. 查看预检结果中的具体失败项",
            "2. 根据每个失败项的建议进行修复",
            "3. 重新运行预检确认修复",
        ],
    },
}


DEFAULT_ERROR_RULE = {
    "title": "部署失败",
    "category": "unknown",
    "human_explanation": "部署过程中发生了未预期的错误。请查看详细日志了解更多信息。",
    "checklist": [
        {
            "action": "查看详细日志",
            "description": "滚动查看下方的部署日志，定位具体错误",
        },
    ],
    "resolution_steps": [
        "1. 查看完整的部署日志",
        "2. 根据日志中的错误信息进行排查",
        "3. 如果问题持续，联系技术支持",
    ],
}


def get_failure_phase_label(phase: Optional[str]) -> str:
    if not phase:
        return "部署过程"
    return FAILURE_PHASES.get(phase, phase)


def get_error_rule(error_code: Optional[str]) -> Dict[str, Any]:
    if not error_code:
        return DEFAULT_ERROR_RULE
    return ERROR_CODE_RULES.get(error_code, DEFAULT_ERROR_RULE)


def analyze_log_excerpt(log_excerpt: Optional[str]) -> Dict[str, Any]:
    if not log_excerpt:
        return {
            "extracted_errors": [],
            "patterns_detected": [],
        }

    extracted_errors = []
    patterns_detected = []

    lines = log_excerpt.split('\n')[-100:]

    error_keywords = [
        ("permission_denied", r"permission denied|Permission denied|EACCES", "权限不足"),
        ("file_not_found", r"No such file|file not found|ENOENT", "文件不存在"),
        ("port_in_use", r"address already in use|port.*already.*bound|0\.0\.0\.0:.*bind", "端口被占用"),
        ("disk_full", r"no space left|disk full|ENOSPC", "磁盘空间不足"),
        ("network_error", r"timeout|connection refused|network.*unreachable|could not resolve", "网络错误"),
        ("image_not_found", r"manifest unknown|image not found|pull access denied", "镜像不存在或无权访问"),
        ("docker_daemon", r"cannot connect to the Docker daemon|docker daemon", "Docker 守护进程未运行"),
        ("out_of_memory", r"out of memory|OOM|memory.*exceeded", "内存不足"),
    ]

    for pattern_key, pattern_re, pattern_label in error_keywords:
        matches = [
            line.strip() for line in lines
            if re.search(pattern_re, line, re.IGNORECASE)
        ]
        if matches:
            patterns_detected.append({
                "key": pattern_key,
                "label": pattern_label,
                "matched_lines": matches[:3],
            })

    error_line_patterns = [
        r"error:|Error:|ERROR:",
        r"fatal:|Fatal:|FATAL:",
        r"exception:|Exception:",
        r"failed:|Failed:|FAILED:",
        r"exit code [1-9]",
    ]

    for line in lines:
        for pattern in error_line_patterns:
            if re.search(pattern, line):
                extracted_errors.append(line.strip()[:200])
                break

    return {
        "extracted_errors": extracted_errors[:10],
        "patterns_detected": patterns_detected,
    }


def explain_failure(
    error_code: Optional[str] = None,
    failure_phase: Optional[str] = None,
    log_excerpt: Optional[str] = None,
) -> Dict[str, Any]:
    rule = get_error_rule(error_code)
    log_analysis = analyze_log_excerpt(log_excerpt)

    result = {
        "error_code": error_code,
        "failure_phase": failure_phase,
        "failure_phase_label": get_failure_phase_label(failure_phase),
        "title": rule["title"],
        "category": rule["category"],
        "human_explanation": rule["human_explanation"],
        "checklist": rule["checklist"],
        "resolution_steps": rule["resolution_steps"],
        "log_analysis": log_analysis,
    }

    if log_analysis["patterns_detected"]:
        additional_notes = []
        for pattern in log_analysis["patterns_detected"]:
            if pattern["key"] == "permission_denied":
                additional_notes.append(
                    "检测到权限问题：请检查文件权限和 Docker 组设置。"
                )
            elif pattern["key"] == "port_in_use":
                additional_notes.append(
                    "检测到端口冲突：请检查 compose 文件中的端口配置或停止占用端口的进程。"
                )
            elif pattern["key"] == "disk_full":
                additional_notes.append(
                    "检测到磁盘空间不足：请清理磁盘空间后重试。"
                )
            elif pattern["key"] == "network_error":
                additional_notes.append(
                    "检测到网络问题：请检查网络连接、防火墙和 DNS 配置。"
                )
        if additional_notes:
            result["additional_notes"] = additional_notes

    if log_excerpt:
        from .config import get_settings
        from .llm_client import LLMClient

        settings = get_settings()
        llm_client = LLMClient(
            enabled=settings.llm_enabled,
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            api_base=settings.llm_api_base,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout,
        )

        if llm_client.is_available():
            llm_result = llm_client.analyze_logs(
                logs=log_excerpt,
                error_code=error_code,
                failure_phase=failure_phase,
            )
            result["llm_analysis"] = llm_result

    return result
