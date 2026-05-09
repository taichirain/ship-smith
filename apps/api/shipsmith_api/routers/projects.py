import uuid
import hashlib
import secrets
import re
import json
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..deps import get_db, get_current_user
from .. import __version__ as API_VERSION
from ..config import get_settings
from ..llm_client import LLMClient
from ..schemas import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectListResponse,
    ProjectWithStatusResponse,
    ProjectStatusDetailResponse,
    DeploymentResponse,
    DeployRequest,
    RollbackRequest,
    RotateAgentTokenResponse,
    TimelineEvent,
    TimelineResponse,
    HealthHistoryResponse,
    HealthHistoryRecord,
    DeploymentMarker,
    DeployCommandGenerateRequest,
    DeployCommandGenerateResponse,
    DeployCommandPlan,
    ProjectTargetCreate,
    ProjectTargetUpdate,
    ProjectTargetResponse,
)

router = APIRouter(prefix="/projects", tags=["projects"])
REPO_ROOT = Path(__file__).resolve().parents[4]
DOC_CONTEXT_FILES = [
    "README.md",
    "docs/user-guide/quickstart.md",
    "docs/user-guide/architecture.md",
    "docs/user-guide/api-reference.md",
]


def _parse_version(version_str: str) -> List[int]:
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)', version_str)
    if match:
        return [int(match.group(1)), int(match.group(2)), int(match.group(3))]
    return [0, 0, 0]


def _is_version_outdated(agent_version: Optional[str], api_version: str) -> bool:
    if not agent_version:
        return True
    agent_parts = _parse_version(agent_version)
    api_parts = _parse_version(api_version)
    return agent_parts < api_parts


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Project, ProjectStatus, Deployment, ProjectAudit, ProjectTarget, DeploymentTarget, DeploymentLog
    return Project, ProjectStatus, Deployment, ProjectAudit, ProjectTarget, DeploymentTarget, DeploymentLog


def _generate_agent_id() -> str:
    return f"agent-{uuid.uuid4().hex[:12]}"


def _generate_agent_token() -> str:
    return secrets.token_urlsafe(48)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_webhook_endpoint_id() -> str:
    return f"wh-{uuid.uuid4().hex[:12]}"


def _get_project_or_404(db: Session, project_id: int):
    Project, _, _, _, _, _, _ = _import_db_models()
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


def _read_context_file(relative_path: str, max_chars: int = 6000) -> Optional[dict]:
    file_path = REPO_ROOT / relative_path
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

    return {
        "path": relative_path,
        "content": content[:max_chars],
    }


def _collect_doc_context() -> List[dict]:
    result: List[dict] = []
    for relative_path in DOC_CONTEXT_FILES:
        item = _read_context_file(relative_path)
        if item:
            result.append(item)
    return result


def _summarize_system_snapshot(snapshot: Optional[dict]) -> dict:
    if not isinstance(snapshot, dict):
        return {
            "os_name": None,
            "shell": None,
            "docker_compose_command": None,
            "agent_version": None,
            "health_status": "unknown",
            "container_count": 0,
        }

    runtime = snapshot.get("runtime", {})
    containers = snapshot.get("containers") or []
    app_health = snapshot.get("app_health") or {}

    if not isinstance(runtime, dict):
        runtime = {}
    if not isinstance(containers, list):
        containers = []
    if not isinstance(app_health, dict):
        app_health = {}

    return {
        "os_name": runtime.get("os_name"),
        "os_release": runtime.get("os_release"),
        "platform": runtime.get("platform"),
        "machine": runtime.get("machine"),
        "shell": runtime.get("shell"),
        "path_separator": runtime.get("path_separator"),
        "docker_compose_command": runtime.get("docker_compose_command"),
        "agent_version": snapshot.get("agent_version"),
        "health_status": app_health.get("status", "unknown"),
        "container_count": len(containers),
    }


def _build_project_summary(project, project_status) -> dict:
    snapshot = project_status.snapshot if project_status and isinstance(project_status.snapshot, dict) else {}
    return {
        "name": project.name,
        "git_repo": project.git_repo,
        "git_branch": project.git_branch,
        "deploy_workdir": project.deploy_workdir,
        "compose_file": project.compose_file,
        "compose_service": project.compose_service,
        "deploy_strategy": project.deploy_strategy,
        "healthcheck_url": project.healthcheck_url,
        "healthcheck_timeout_seconds": project.healthcheck_timeout_seconds,
        "flags_file_path": project.flags_file_path,
        "runbook": {
            "notes": project.notes,
            "release_notes_hint": project.release_notes_hint,
            "troubleshooting_hint": project.troubleshooting_hint,
            "admin_url": project.admin_url,
            "metrics_url": project.metrics_url,
            "logs_url": project.logs_url,
            "ssh_hint": project.ssh_hint,
        },
        "current_status": {
            "health_status": project_status.health_status if project_status else "unknown",
            "agent_last_seen_at": project_status.agent_last_seen_at.isoformat() if project_status and project_status.agent_last_seen_at else None,
            "current_commit_hash": project_status.current_commit_hash if project_status else None,
            "runtime": snapshot.get("runtime") if isinstance(snapshot, dict) else None,
        },
    }


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, ProjectStatus, _, _, ProjectTarget, _, _ = _import_db_models()

    agent_id = _generate_agent_id()
    agent_token = _generate_agent_token()
    agent_token_hash = _hash_token(agent_token)

    project = Project(
        name=data.name,
        environment=data.environment,
        git_repo=data.git_repo,
        git_branch=data.git_branch,
        deploy_workdir=data.deploy_workdir,
        compose_file=data.compose_file,
        compose_service=data.compose_service,
        deploy_strategy=data.deploy_strategy,
        healthcheck_url=data.healthcheck_url,
        healthcheck_timeout_seconds=data.healthcheck_timeout_seconds,
        flags_file_path=data.flags_file_path,
        agent_id=agent_id,
        agent_token_hash=agent_token_hash,
        webhook_endpoint_id=_generate_webhook_endpoint_id(),
    )
    db.add(project)
    db.flush()

    project_status = ProjectStatus(project_id=project.id)
    db.add(project_status)

    project_target = ProjectTarget(
        project_id=project.id,
        agent_id=agent_id,
        name=f"{data.name}-default",
        role="primary",
        enabled=True,
        order_index=0,
    )
    db.add(project_target)

    db.commit()
    db.refresh(project)

    response = ProjectResponse.model_validate(project)
    response.agent_token = agent_token
    return response


@router.get("", response_model=List[ProjectListResponse])
async def list_projects(
    health_status: Optional[str] = Query(default=None, description="Filter by health status"),
    environment: Optional[str] = Query(default=None, description="Filter by environment: production, staging, development, testing, other"),
    q: Optional[str] = Query(default=None, description="Search query for name, git_repo"),
    sort_by: Optional[str] = Query(
        default="created_at",
        description="Sort by: created_at, name, last_deployment_at, agent_last_seen_at, health_status_priority"
    ),
    sort_order: Optional[str] = Query(default="desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlalchemy import or_
    Project, ProjectStatus, Deployment, _, _, _, _ = _import_db_models()

    query = db.query(Project)

    if q:
        query = query.filter(
            or_(
                Project.name.ilike(f"%{q}%"),
                Project.git_repo.ilike(f"%{q}%"),
            )
        )

    if environment:
        query = query.filter(Project.environment == environment)

    if health_status:
        query = query.join(ProjectStatus, Project.id == ProjectStatus.project_id).filter(
            ProjectStatus.health_status == health_status
        )

    projects = query.all()

    last_deployment_map = {}
    if projects:
        project_ids = [p.id for p in projects]
        all_deployments = (
            db.query(Deployment)
            .filter(Deployment.project_id.in_(project_ids))
            .order_by(
                Deployment.project_id,
                Deployment.queued_at.desc(),
            )
            .all()
        )
        seen_projects = set()
        for d in all_deployments:
            if d.project_id not in seen_projects:
                seen_projects.add(d.project_id)
                last_deployment_map[d.project_id] = {
                    "status": d.status,
                    "at": d.finished_at or d.queued_at,
                }

    result = []
    for p in projects:
        project_dict = {
            "id": p.id,
            "name": p.name,
            "environment": p.environment,
            "git_repo": p.git_repo,
            "git_branch": p.git_branch,
            "deploy_workdir": p.deploy_workdir,
            "deploy_strategy": p.deploy_strategy,
            "health_status": "unknown",
            "agent_last_seen_at": None,
            "current_commit_hash": None,
            "last_deployment_status": None,
            "last_deployment_at": None,
            "webhook_endpoint_id": p.webhook_endpoint_id,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }

        if p.status:
            project_dict["health_status"] = p.status.health_status or "unknown"
            project_dict["agent_last_seen_at"] = p.status.agent_last_seen_at
            project_dict["current_commit_hash"] = p.status.current_commit_hash

            snapshot = p.status.snapshot or {}
            if isinstance(snapshot, dict):
                agent_version = snapshot.get("agent_version")
                project_dict["agent_version"] = agent_version
                project_dict["agent_version_outdated"] = _is_version_outdated(agent_version, API_VERSION)

        deploy_info = last_deployment_map.get(p.id)
        if deploy_info:
            project_dict["last_deployment_status"] = deploy_info["status"]
            project_dict["last_deployment_at"] = deploy_info["at"]

        result.append(project_dict)

    def get_sort_key(item):
        if sort_by == "name":
            return item["name"].lower()
        elif sort_by == "last_deployment_at":
            return item["last_deployment_at"] or datetime.min
        elif sort_by == "agent_last_seen_at":
            return item["agent_last_seen_at"] or datetime.min
        elif sort_by == "health_status_priority":
            priority = {"unhealthy": 0, "degraded": 1, "unknown": 2, "healthy": 3}
            return priority.get(item["health_status"], 99)
        else:
            return item["created_at"]

    reverse_sort = sort_order == "desc"
    if sort_by == "health_status_priority":
        reverse_sort = False
    result.sort(key=get_sort_key, reverse=reverse_sort)

    return [ProjectListResponse.model_validate(p) for p in result]


@router.get("/{project_id}", response_model=ProjectWithStatusResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    project = _get_project_or_404(db, project_id)
    
    response_data = {
        "id": project.id,
        "name": project.name,
        "git_repo": project.git_repo,
        "git_branch": project.git_branch,
        "deploy_workdir": project.deploy_workdir,
        "compose_file": project.compose_file,
        "compose_service": project.compose_service,
        "deploy_strategy": project.deploy_strategy,
        "healthcheck_url": project.healthcheck_url,
        "healthcheck_timeout_seconds": project.healthcheck_timeout_seconds,
        "flags_file_path": project.flags_file_path,
        "agent_id": project.agent_id,
        "webhook_endpoint_id": project.webhook_endpoint_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "health_status": project.status.health_status if project.status else "unknown",
        "agent_last_seen_at": project.status.agent_last_seen_at if project.status else None,
        "current_commit_hash": project.status.current_commit_hash if project.status else None,
    }
    
    return ProjectWithStatusResponse.model_validate(response_data)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, _, ProjectAudit, _, _, _ = _import_db_models()
    project = _get_project_or_404(db, project_id)
    
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    
    old_values = {}
    new_values = {}
    
    for field, value in update_data.items():
        old_val = getattr(project, field)
        old_values[field] = old_val
        new_values[field] = value
        setattr(project, field, value)
    
    project.updated_at = datetime.utcnow()
    
    audit = ProjectAudit(
        project_id=project.id,
        action="update",
        changed_by=current_user.get("username"),
        old_values=old_values,
        new_values=new_values,
    )
    db.add(audit)
    
    db.commit()
    db.refresh(project)
    
    response = ProjectResponse.model_validate(project)
    if "webhook_secret" in update_data:
        response.webhook_secret = update_data["webhook_secret"]
    return response


@router.post("/{project_id}/rotate-agent-token", response_model=RotateAgentTokenResponse)
async def rotate_agent_token(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    project = _get_project_or_404(db, project_id)
    
    new_token = _generate_agent_token()
    project.agent_token_hash = _hash_token(new_token)
    project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(project)
    
    return RotateAgentTokenResponse(
        agent_id=project.agent_id,
        agent_token=new_token,
    )


def _get_core_url(settings, override: Optional[str] = None) -> str:
    if override:
        return override.rstrip("/")
    if settings.public_core_url:
        return settings.public_core_url.rstrip("/")
    return ""


def _determine_onboarding_status(project_status, project_created_at: datetime, now: datetime):
    from datetime import timedelta
    from ..schemas import AgentOnboardingStatus

    if project_status and project_status.agent_first_seen_at is not None:
        return AgentOnboardingStatus.ONLINE

    age_minutes = (now - project_created_at).total_seconds() / 60
    if age_minutes > 60:
        return AgentOnboardingStatus.EXPIRED

    return AgentOnboardingStatus.WAITING


def _get_troubleshooting_hints(status, project_status, project) -> List[str]:
    from ..schemas import AgentOnboardingStatus

    hints = []

    if status == AgentOnboardingStatus.WAITING:
        hints.append("在目标服务器上执行安装命令以安装 Agent")
        hints.append("确保服务器能访问 Core URL")
        hints.append("检查 Agent 服务是否已启动")
        hints.append("检查防火墙是否允许出站连接到 Core")
    elif status == AgentOnboardingStatus.EXPIRED:
        hints.append("项目创建超过 60 分钟仍未看到 Agent 上线")
        hints.append("点击 '重新生成安装命令' 获取新命令")
        hints.append("或使用 'Rotate Agent Token' 重新获取 token")
        hints.append("检查服务器网络连接和 DNS 解析")
    elif status == AgentOnboardingStatus.ONLINE:
        hints.append("Agent 已成功连接到 Core")
        hints.append("可以开始进行首次部署了")

    if project_status and project_status.agent_last_seen_at is None and status != AgentOnboardingStatus.ONLINE:
        hints.append("尚未收到任何来自 Agent 的心跳")

    return hints


@router.get("/{project_id}/onboarding")
async def get_project_onboarding(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, ProjectStatus, _, _, _, _, _ = _import_db_models()
    from ..schemas import AgentOnboardingStatus, OnboardingStatusResponse
    from datetime import datetime

    project = _get_project_or_404(db, project_id)
    settings = get_settings()
    now = datetime.utcnow()

    core_url = _get_core_url(settings)
    status = AgentOnboardingStatus.WAITING
    agent_first_seen_at = None
    agent_last_seen_at = None
    health_status = "unknown"

    if project.status:
        status = _determine_onboarding_status(project.status, project.created_at, now)
        agent_first_seen_at = project.status.agent_first_seen_at
        agent_last_seen_at = project.status.agent_last_seen_at
        health_status = project.status.health_status

    hints = _get_troubleshooting_hints(status, project.status, project)

    response = {
        "project_id": project.id,
        "agent_id": project.agent_id,
        "core_url": core_url,
        "workdir": project.deploy_workdir,
        "status": status,
        "agent_first_seen_at": agent_first_seen_at,
        "agent_last_seen_at": agent_last_seen_at,
        "health_status": health_status,
        "install_command": None,
        "install_command_expires_at": None,
        "manual_steps_available": True,
        "troubleshooting_hints": hints,
    }

    return response


@router.post("/{project_id}/install-command")
async def generate_install_command(
    project_id: int,
    data: dict = {},
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, ProjectStatus, _, _, _, _, _ = _import_db_models()
    from ..schemas import (
        InstallCommandRequest,
        InstallCommandResponse,
        InstallMode,
        TargetPlatform,
    )
    from datetime import datetime, timedelta

    project = _get_project_or_404(db, project_id)
    settings = get_settings()

    try:
        req = InstallCommandRequest(**data)
    except Exception:
        req = InstallCommandRequest()

    core_url = _get_core_url(settings, req.core_url)
    workdir = req.workdir or project.deploy_workdir

    new_token = _generate_agent_token()
    project.agent_token_hash = _hash_token(new_token)
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)

    if not core_url:
        core_url_placeholder = "http://your-core-host:8000"
    else:
        core_url_placeholder = core_url

    notes = []
    command = ""

    if req.target_platform == TargetPlatform.LINUX_SYSTEMD:
        command = (
            f'curl -fsSL https://shipsmith.example.com/install.sh | '
            f'sh -s -- --project-id {project.id} --agent-id {project.agent_id} '
            f'--core-url "{core_url_placeholder}/api/v1" '
            f'--token "{new_token}" '
            f'--workdir "{workdir}"'
        )
        notes.append("此命令需要 root 权限或 sudo 访问")
        notes.append("脚本会下载 Agent 二进制、配置 systemd 服务并启动")
        notes.append("执行前请确保服务器已安装 curl 和 systemd")
    elif req.target_platform == TargetPlatform.LINUX_DOCKER:
        command = (
            f'docker run -d --name shipsmith-agent-{project.id} '
            f'--restart always '
            f'-e SHIPSMITH_CORE_URL="{core_url_placeholder}/api/v1" '
            f'-e SHIPSMITH_AGENT_TOKEN="{new_token}" '
            f'-e SHIPSMITH_PROJECT_ID={project.id} '
            f'-e SHIPSMITH_AGENT_ID={project.agent_id} '
            f'-e SHIPSMITH_WORKDIR="{workdir}" '
            f'-v /var/run/docker.sock:/var/run/docker.sock '
            f'-v {workdir}:{workdir} '
            f'shipsmith/agent:latest'
        )
        notes.append("此方式使用 Docker 运行 Agent")
        notes.append("确保服务器已安装 Docker")
        notes.append("/var/run/docker.sock 挂载用于执行容器操作")
    elif req.target_platform == TargetPlatform.MANUAL:
        command = (
            f'# 手动安装步骤\n'
            f'export SHIPSMITH_CORE_URL="{core_url_placeholder}/api/v1"\n'
            f'export SHIPSMITH_AGENT_TOKEN="{new_token}"\n'
            f'export SHIPSMITH_PROJECT_ID={project.id}\n'
            f'export SHIPSMITH_AGENT_ID={project.agent_id}\n'
            f'export SHIPSMITH_WORKDIR="{workdir}"\n'
            f'# 然后运行: shipsmith-agent'
        )
        notes.append("手动安装模式 - 请按步骤执行")
        notes.append("需要自行配置服务管理（如 systemd 或 supervisor）")

    if req.install_mode == InstallMode.DRY_RUN:
        notes.insert(0, "⚠️ DRY-RUN 模式：此命令不会实际执行任何安装操作")

    expires_at = datetime.utcnow() + timedelta(hours=1)

    response = {
        "project_id": project.id,
        "install_mode": req.install_mode.value,
        "target_platform": req.target_platform.value,
        "command": command,
        "expires_at": expires_at,
        "manual_install_url": None,
        "notes": notes,
        "agent_id": project.agent_id,
        "core_url": f"{core_url_placeholder}/api/v1" if core_url_placeholder else "",
        "workdir": workdir,
    }

    return response


@router.get("/{project_id}/status", response_model=ProjectStatusDetailResponse)
async def get_project_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, ProjectStatus, _, _, _, _, _ = _import_db_models()
    
    project = _get_project_or_404(db, project_id)
    
    if not project.status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project status not found",
        )
    
    status_data = {
        "project_id": project.status.project_id,
        "agent_last_seen_at": project.status.agent_last_seen_at,
        "health_status": project.status.health_status,
        "current_commit_hash": project.status.current_commit_hash,
        "last_deployment_id": project.status.last_deployment_id,
        "updated_at": project.status.updated_at,
    }
    
    snapshot = project.status.snapshot or {}
    if isinstance(snapshot, dict):
        system = snapshot.get("system", {})
        if isinstance(system, dict):
            status_data["cpu_percent"] = system.get("cpu_percent")
            status_data["mem_used_mb"] = system.get("mem_used_mb")
            status_data["mem_total_mb"] = system.get("mem_total_mb")
            status_data["disk_used_percent"] = system.get("disk_used_percent")
        status_data["containers"] = snapshot.get("containers")
        status_data["app_health"] = snapshot.get("app_health")
        status_data["runtime"] = snapshot.get("runtime")
        agent_version = snapshot.get("agent_version")
        status_data["agent_version"] = agent_version
        status_data["agent_version_outdated"] = _is_version_outdated(agent_version, API_VERSION)
    
    return ProjectStatusDetailResponse.model_validate(status_data)


@router.post("/{project_id}/generate-deploy-commands", response_model=DeployCommandGenerateResponse)
async def generate_deploy_commands(
    project_id: int,
    data: DeployCommandGenerateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    project = _get_project_or_404(db, project_id)
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

    if not llm_client.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured or disabled",
        )

    snapshot = project.status.snapshot if project.status and isinstance(project.status.snapshot, dict) else {}
    docs_context = _collect_doc_context()
    project_summary = _build_project_summary(project, project.status)
    system_summary = _summarize_system_snapshot(snapshot)

    result = llm_client.generate_deploy_commands(
        project_summary=project_summary,
        system_info=system_summary,
        docs_context=docs_context,
        user_goal=data.user_goal,
        preferred_shell=data.preferred_shell,
        extra_context=data.extra_context,
    )

    if result.get("llm_generation_failed"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": result.get("llm_error", "LLM generation failed"),
                "raw_response": result.get("llm_raw_response"),
            },
        )

    plan = result.get("plan") or {}
    commands = plan.get("commands") or []
    if not isinstance(commands, list):
        commands = []

    assumptions = plan.get("assumptions") or []
    prechecks = plan.get("prechecks") or []
    verification = plan.get("verification") or []

    if not assumptions:
        assumptions = ["未检测到完整的目标机运行时信息时，命令按通用 shell 形式生成。"]

    return DeployCommandGenerateResponse(
        project_id=project.id,
        source_files=[item["path"] for item in docs_context],
        system_summary=system_summary,
        assumptions=assumptions,
        prechecks=prechecks,
        commands=[DeployCommandPlan.model_validate(item) for item in commands],
        verification=verification,
        explanation=plan.get("explanation", ""),
        llm_provider=result.get("llm_provider"),
        llm_model=result.get("llm_model"),
        llm_duration_ms=result.get("llm_duration_ms"),
    )


@router.post("/{project_id}/deploy", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def deploy_project(
    project_id: int,
    data: DeployRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, Deployment, _, ProjectTarget, DeploymentTarget, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    existing_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another deployment is already in progress for this project",
        )

    enabled_targets = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == project_id,
            ProjectTarget.enabled == True,
        )
        .order_by(ProjectTarget.order_index.asc(), ProjectTarget.id.asc())
        .all()
    )
    if not enabled_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled targets for this project",
        )

    deploy_mode = data.deploy_mode or "all-at-once"
    if deploy_mode not in ["all-at-once", "rolling"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid deploy_mode. Must be 'all-at-once' or 'rolling'",
        )

    deployment = Deployment(
        project_id=project_id,
        kind="deploy",
        status="queued",
        deploy_mode=deploy_mode,
        trigger_source=data.trigger_source,
        commit_hash=data.commit_hash,
        triggered_by=current_user.get("username"),
        queued_at=datetime.utcnow(),
    )
    db.add(deployment)
    db.flush()

    for idx, target in enumerate(enabled_targets):
        dt_status = "queued"
        if deploy_mode == "rolling" and idx > 0:
            dt_status = "blocked"

        deployment_target = DeploymentTarget(
            deployment_id=deployment.id,
            project_target_id=target.id,
            agent_id=target.agent_id,
            status=dt_status,
        )
        db.add(deployment_target)

    db.commit()
    db.refresh(deployment)

    return DeploymentResponse.model_validate(deployment)


@router.get("/{project_id}/deployments", response_model=List[DeploymentResponse])
async def list_deployments(
    project_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, Deployment, _, _, _, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    deployments = (
        db.query(Deployment)
        .filter(Deployment.project_id == project_id)
        .order_by(Deployment.queued_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [DeploymentResponse.model_validate(d) for d in deployments]


@router.post("/{project_id}/rollback", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def rollback_project(
    project_id: int,
    data: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, Deployment, _, ProjectTarget, DeploymentTarget, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    target_deployment = (
        db.query(Deployment)
        .filter(
            Deployment.id == data.target_deployment_id,
            Deployment.project_id == project_id,
            Deployment.status == "success",
        )
        .first()
    )
    if not target_deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target deployment not found or not successful",
        )

    existing_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another deployment is already in progress for this project",
        )

    enabled_targets = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == project_id,
            ProjectTarget.enabled == True,
        )
        .order_by(ProjectTarget.order_index.asc(), ProjectTarget.id.asc())
        .all()
    )
    if not enabled_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled targets for this project",
        )

    rollback_deployment = Deployment(
        project_id=project_id,
        kind="rollback",
        status="queued",
        deploy_mode="all-at-once",
        trigger_source="rollback",
        commit_hash=target_deployment.commit_hash,
        target_deployment_id=data.target_deployment_id,
        triggered_by=current_user.get("username"),
        queued_at=datetime.utcnow(),
    )
    db.add(rollback_deployment)
    db.flush()

    for target in enabled_targets:
        deployment_target = DeploymentTarget(
            deployment_id=rollback_deployment.id,
            project_target_id=target.id,
            agent_id=target.agent_id,
            status="queued",
        )
        db.add(deployment_target)

    db.commit()
    db.refresh(rollback_deployment)

    return DeploymentResponse.model_validate(rollback_deployment)


@router.post("/{project_id}/rollback-to-last-success", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def rollback_to_last_success(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, Deployment, _, ProjectTarget, DeploymentTarget, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    last_success = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status == "success",
        )
        .order_by(Deployment.finished_at.desc())
        .first()
    )

    if not last_success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No successful deployment found for this project",
        )

    existing_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another deployment is already in progress for this project",
        )

    enabled_targets = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == project_id,
            ProjectTarget.enabled == True,
        )
        .order_by(ProjectTarget.order_index.asc(), ProjectTarget.id.asc())
        .all()
    )
    if not enabled_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled targets for this project",
        )

    rollback_deployment = Deployment(
        project_id=project_id,
        kind="rollback",
        status="queued",
        deploy_mode="all-at-once",
        trigger_source="rollback_to_last_success",
        commit_hash=last_success.commit_hash,
        target_deployment_id=last_success.id,
        triggered_by=current_user.get("username"),
        queued_at=datetime.utcnow(),
    )
    db.add(rollback_deployment)
    db.flush()

    for target in enabled_targets:
        deployment_target = DeploymentTarget(
            deployment_id=rollback_deployment.id,
            project_target_id=target.id,
            agent_id=target.agent_id,
            status="queued",
        )
        db.add(deployment_target)

    db.commit()
    db.refresh(rollback_deployment)

    return DeploymentResponse.model_validate(rollback_deployment)


@router.post("/{project_id}/generate-webhook-secret")
async def generate_webhook_secret(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    project = _get_project_or_404(db, project_id)
    
    new_secret = secrets.token_urlsafe(32)
    project.webhook_secret = new_secret
    project.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(project)
    
    return {
        "ok": True,
        "webhook_secret": new_secret,
        "webhook_endpoint": f"/api/v1/webhooks/{project.webhook_endpoint_id}/github",
    }


@router.post("/{project_id}/precheck", status_code=status.HTTP_202_ACCEPTED)
async def trigger_precheck(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Deployment

    project = _get_project_or_404(db, project_id)

    existing_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another task is already in progress for this project",
        )

    precheck_deployment = Deployment(
        project_id=project_id,
        kind="precheck",
        status="queued",
        trigger_source="manual",
        triggered_by=current_user.get("username"),
        queued_at=datetime.utcnow(),
    )
    db.add(precheck_deployment)
    db.commit()
    db.refresh(precheck_deployment)

    return {
        "ok": True,
        "deployment_id": precheck_deployment.id,
        "status": "queued",
        "message": "Precheck task queued. Poll for status or check latest precheck result.",
    }


@router.get("/{project_id}/prechecks")
async def list_prechecks(
    project_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import AgentPrecheck

    project = _get_project_or_404(db, project_id)

    prechecks = (
        db.query(AgentPrecheck)
        .filter(AgentPrecheck.project_id == project_id)
        .order_by(AgentPrecheck.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "total": len(prechecks),
        "prechecks": [
            {
                "id": p.id,
                "project_id": p.project_id,
                "agent_id": p.agent_id,
                "overall_status": p.overall_status,
                "summary": p.summary,
                "result_json": p.result_json,
                "started_at": p.started_at.isoformat() if p.started_at else None,
                "finished_at": p.finished_at.isoformat() if p.finished_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in prechecks
        ],
    }


@router.get("/{project_id}/prechecks/latest")
async def get_latest_precheck(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import AgentPrecheck, Deployment

    project = _get_project_or_404(db, project_id)

    pending_task = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.kind == "precheck",
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )

    latest_precheck = (
        db.query(AgentPrecheck)
        .filter(AgentPrecheck.project_id == project_id)
        .order_by(AgentPrecheck.created_at.desc())
        .first()
    )

    result = {
        "pending_task": None,
        "latest_precheck": None,
    }

    if pending_task:
        result["pending_task"] = {
            "id": pending_task.id,
            "status": pending_task.status,
            "started_at": pending_task.started_at.isoformat() if pending_task.started_at else None,
            "queued_at": pending_task.queued_at.isoformat() if pending_task.queued_at else None,
        }

    if latest_precheck:
        result["latest_precheck"] = {
            "id": latest_precheck.id,
            "project_id": latest_precheck.project_id,
            "agent_id": latest_precheck.agent_id,
            "overall_status": latest_precheck.overall_status,
            "summary": latest_precheck.summary,
            "result_json": latest_precheck.result_json,
            "started_at": latest_precheck.started_at.isoformat() if latest_precheck.started_at else None,
            "finished_at": latest_precheck.finished_at.isoformat() if latest_precheck.finished_at else None,
            "created_at": latest_precheck.created_at.isoformat() if latest_precheck.created_at else None,
        }

    return result


@router.get("/{project_id}/timeline", response_model=TimelineResponse)
async def get_project_timeline(
    project_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import (
        Project,
        ProjectStatus,
        Deployment,
        FeatureFlag,
        FlagAudit,
        WebhookDelivery,
        Heartbeat,
        ProjectAudit,
    )

    project = _get_project_or_404(db, project_id)

    all_events = []

    deployments = (
        db.query(Deployment)
        .filter(Deployment.project_id == project_id)
        .order_by(Deployment.queued_at.desc())
        .all()
    )
    for d in deployments:
        if d.kind == "rollback":
            event_type_val = f"rollback_{d.status}"
            title = f"Rollback #{d.id} {d.status}"
        else:
            event_type_val = f"deployment_{d.status}"
            title = f"Deploy #{d.id} {d.status}"

        summary_parts = []
        if d.commit_hash:
            summary_parts.append(f"Commit: {d.commit_hash[:8]}")
        if d.trigger_source:
            summary_parts.append(f"Source: {d.trigger_source}")

        occurred_at = d.finished_at or d.started_at or d.queued_at

        all_events.append({
            "id": f"deploy-{d.id}",
            "type": event_type_val,
            "occurred_at": occurred_at,
            "title": title,
            "summary": " | ".join(summary_parts) if summary_parts else None,
            "actor": d.triggered_by,
            "metadata": {
                "deployment_id": d.id,
                "kind": d.kind,
                "status": d.status,
                "commit_hash": d.commit_hash,
                "trigger_source": d.trigger_source,
                "error_code": d.error_code,
                "failure_phase": d.failure_phase,
            },
        })

    flag_audits = (
        db.query(FlagAudit)
        .filter(FlagAudit.project_id == project_id)
        .order_by(FlagAudit.created_at.desc())
        .all()
    )
    for audit in flag_audits:
        if audit.old_enabled is None:
            event_type_val = "flag_created"
            title = f"Flag '{audit.flag_key}' created"
        else:
            old_state = "enabled" if audit.old_enabled else "disabled"
            new_state = "enabled" if audit.new_enabled else "disabled"
            if old_state != new_state:
                event_type_val = "flag_updated"
                title = f"Flag '{audit.flag_key}' {old_state} → {new_state}"
            else:
                event_type_val = "flag_updated"
                title = f"Flag '{audit.flag_key}' updated"

        all_events.append({
            "id": f"flag-audit-{audit.id}",
            "type": event_type_val,
            "occurred_at": audit.created_at,
            "title": title,
            "summary": f"Changed by: {audit.changed_by}",
            "actor": audit.changed_by,
            "metadata": {
                "flag_key": audit.flag_key,
                "old_enabled": audit.old_enabled,
                "new_enabled": audit.new_enabled,
            },
        })

    flags = (
        db.query(FeatureFlag)
        .filter(FeatureFlag.project_id == project_id)
        .all()
    )
    for f in flags:
        if f.archived and f.archived_at:
            all_events.append({
                "id": f"flag-archive-{f.id}",
                "type": "flag_archived",
                "occurred_at": f.archived_at,
                "title": f"Flag '{f.key}' archived",
                "summary": f"Archived by: {f.archived_by}" if f.archived_by else None,
                "actor": f.archived_by,
                "metadata": {
                    "flag_id": f.id,
                    "flag_key": f.key,
                },
            })
        if not f.archived and f.archived_at:
            all_events.append({
                "id": f"flag-unarchive-{f.id}",
                "type": "flag_unarchived",
                "occurred_at": f.updated_at,
                "title": f"Flag '{f.key}' unarchived",
                "summary": f"Unarchived by: {f.updated_by}" if f.updated_by else None,
                "actor": f.updated_by,
                "metadata": {
                    "flag_id": f.id,
                    "flag_key": f.key,
                },
            })

    webhook_deliveries = (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.project_id == project_id)
        .order_by(WebhookDelivery.created_at.desc())
        .all()
    )
    for delivery in webhook_deliveries:
        payload = delivery.payload or {}
        ref = payload.get("ref", "")
        branch = None
        if ref and ref.startswith("refs/heads/"):
            branch = ref[len("refs/heads/"):]

        all_events.append({
            "id": f"webhook-{delivery.id}",
            "type": "webhook_accepted",
            "occurred_at": delivery.created_at,
            "title": f"Webhook {delivery.event_type} received",
            "summary": f"Source: {delivery.source}" + (f" | Branch: {branch}" if branch else ""),
            "actor": None,
            "metadata": {
                "delivery_id": delivery.delivery_id,
                "source": delivery.source,
                "event_type": delivery.event_type,
                "branch": branch,
            },
        })

    project_audits = (
        db.query(ProjectAudit)
        .filter(ProjectAudit.project_id == project_id)
        .order_by(ProjectAudit.created_at.desc())
        .all()
    )
    for audit in project_audits:
        changed_fields = list(audit.new_values.keys())
        fields_str = ", ".join(changed_fields[:3])
        if len(changed_fields) > 3:
            fields_str += f" +{len(changed_fields) - 3} more"

        all_events.append({
            "id": f"config-{audit.id}",
            "type": "config_updated",
            "occurred_at": audit.created_at,
            "title": f"Project config updated" if fields_str else "Project config updated",
            "summary": f"Changed fields: {fields_str}" if fields_str else None,
            "actor": audit.changed_by,
            "metadata": {
                "old_values": audit.old_values,
                "new_values": audit.new_values,
                "changed_fields": changed_fields,
            },
        })

    heartbeats = (
        db.query(Heartbeat)
        .filter(Heartbeat.project_id == project_id)
        .order_by(Heartbeat.created_at.desc())
        .all()
    )
    if heartbeats:
        prev_seen = None
        for hb in reversed(heartbeats):
            if prev_seen is None:
                all_events.append({
                    "id": f"hb-first-{hb.id}",
                    "type": "agent_recovered",
                    "occurred_at": hb.created_at,
                    "title": "Agent came online",
                    "summary": f"Agent ID: {hb.agent_id}",
                    "actor": None,
                    "metadata": {
                        "agent_id": hb.agent_id,
                        "heartbeat_id": hb.id,
                    },
                })
            else:
                gap = hb.created_at - prev_seen
                if gap > timedelta(minutes=5):
                    all_events.append({
                        "id": f"hb-offline-{prev_seen.timestamp()}",
                        "type": "agent_offline",
                        "occurred_at": prev_seen + timedelta(minutes=2),
                        "title": "Agent went offline",
                        "summary": f"Gap of {int(gap.total_seconds() / 60)} minutes detected",
                        "actor": None,
                        "metadata": {
                            "agent_id": hb.agent_id,
                            "gap_minutes": int(gap.total_seconds() / 60),
                        },
                    })
                    all_events.append({
                        "id": f"hb-recovered-{hb.id}",
                        "type": "agent_recovered",
                        "occurred_at": hb.created_at,
                        "title": "Agent recovered",
                        "summary": f"Agent ID: {hb.agent_id}",
                        "actor": None,
                        "metadata": {
                            "agent_id": hb.agent_id,
                            "heartbeat_id": hb.id,
                        },
                    })
            prev_seen = hb.created_at

        if project.status and project.status.agent_last_seen_at:
            now = datetime.utcnow()
            time_since_last = now - project.status.agent_last_seen_at
            if time_since_last > timedelta(minutes=5):
                all_events.append({
                    "id": f"hb-offline-current",
                    "type": "agent_offline",
                    "occurred_at": project.status.agent_last_seen_at + timedelta(minutes=2),
                    "title": "Agent currently offline",
                    "summary": f"Last seen {int(time_since_last.total_seconds() / 60)} minutes ago",
                    "actor": None,
                    "metadata": {
                        "last_seen_at": project.status.agent_last_seen_at.isoformat() if project.status.agent_last_seen_at else None,
                    },
                })

    valid_event_types = {
        "deployment_queued", "deployment_running", "deployment_success", "deployment_failed",
        "rollback_queued", "rollback_running", "rollback_success", "rollback_failed",
        "flag_created", "flag_updated", "flag_archived", "flag_unarchived",
        "config_updated",
        "webhook_accepted", "webhook_ignored",
        "agent_offline", "agent_recovered",
    }

    filtered_events = [e for e in all_events if e["type"] in valid_event_types]

    if event_type:
        filtered_events = [e for e in filtered_events if e["type"] == event_type]

    filtered_events.sort(key=lambda x: x["occurred_at"], reverse=True)

    total = len(filtered_events)
    paginated_events = filtered_events[offset:offset + limit]

    return TimelineResponse(
        events=[TimelineEvent(**e) for e in paginated_events],
        total=total,
    )


@router.get("/{project_id}/health-history", response_model=HealthHistoryResponse)
async def get_project_health_history(
    project_id: int,
    time_range: str = Query(default="24h", description="Time range: 24h or 7d"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Heartbeat, Deployment

    project = _get_project_or_404(db, project_id)

    if time_range == "24h":
        hours = 24
    elif time_range == "7d":
        hours = 7 * 24
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid time_range. Must be '24h' or '7d'",
        )

    now = datetime.utcnow()
    start_time = now - timedelta(hours=hours)

    heartbeats = (
        db.query(Heartbeat)
        .filter(
            Heartbeat.project_id == project_id,
            Heartbeat.created_at >= start_time,
        )
        .order_by(Heartbeat.created_at.asc())
        .all()
    )

    records = []
    for hb in heartbeats:
        payload = hb.payload or {}
        app_health = payload.get("app_health", {}) if isinstance(payload, dict) else {}
        
        health_status = "unknown"
        response_ms = None
        
        if isinstance(app_health, dict):
            health_status = app_health.get("status", "unknown")
            response_ms = app_health.get("response_ms")

        records.append(HealthHistoryRecord(
            timestamp=hb.created_at,
            health_status=health_status,
            response_ms=response_ms,
            heartbeat_present=True,
        ))

    deployments = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.queued_at >= start_time,
        )
        .order_by(Deployment.queued_at.asc())
        .all()
    )

    markers = []
    for d in deployments:
        marker_time = d.finished_at or d.started_at or d.queued_at
        markers.append(DeploymentMarker(
            timestamp=marker_time,
            deployment_id=d.id,
            status=d.status,
            kind=d.kind,
            commit_hash=d.commit_hash,
        ))

    return HealthHistoryResponse(
        records=records,
        deployment_markers=markers,
    )


@router.get("/{project_id}/targets", response_model=List[ProjectTargetResponse])
async def list_project_targets(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, _, _, ProjectTarget, _, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    targets = (
        db.query(ProjectTarget)
        .filter(ProjectTarget.project_id == project_id)
        .order_by(ProjectTarget.order_index.asc(), ProjectTarget.id.asc())
        .all()
    )

    return [ProjectTargetResponse.model_validate(t) for t in targets]


@router.post("/{project_id}/targets", response_model=ProjectTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_project_target(
    project_id: int,
    data: ProjectTargetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, _, _, ProjectTarget, _, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    existing = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == project_id,
            ProjectTarget.agent_id == data.agent_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent {data.agent_id} is already bound to this project",
        )

    if data.order_index is None:
        max_order = (
            db.query(ProjectTarget.order_index)
            .filter(ProjectTarget.project_id == project_id)
            .order_by(ProjectTarget.order_index.desc())
            .first()
        )
        order_index = (max_order[0] + 1) if max_order else 0
    else:
        order_index = data.order_index

    target = ProjectTarget(
        project_id=project_id,
        agent_id=data.agent_id,
        name=data.name,
        role=data.role,
        enabled=data.enabled,
        order_index=order_index,
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    return ProjectTargetResponse.model_validate(target)


@router.patch("/{project_id}/targets/{target_id}", response_model=ProjectTargetResponse)
async def update_project_target(
    project_id: int,
    target_id: int,
    data: ProjectTargetUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, _, _, ProjectTarget, _, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    target = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.id == target_id,
            ProjectTarget.project_id == project_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("enabled") is False:
        enabled_count = (
            db.query(ProjectTarget)
            .filter(
                ProjectTarget.project_id == project_id,
                ProjectTarget.enabled == True,
                ProjectTarget.id != target_id,
            )
            .count()
        )
        if enabled_count < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one enabled target is required",
            )

    for field, value in update_data.items():
        setattr(target, field, value)

    target.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target)

    return ProjectTargetResponse.model_validate(target)


@router.delete("/{project_id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_target(
    project_id: int,
    target_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, _, _, _, ProjectTarget, _, _ = _import_db_models()

    project = _get_project_or_404(db, project_id)

    target = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.id == target_id,
            ProjectTarget.project_id == project_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found",
        )

    enabled_count = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == project_id,
            ProjectTarget.enabled == True,
            ProjectTarget.id != target_id,
        )
        .count()
    )
    if target.enabled and enabled_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last enabled target",
        )

    db.delete(target)
    db.commit()


class GitBranchesRequest(BaseModel):
    git_repo: str


class GitBranchInfo(BaseModel):
    name: str
    is_default: bool = False


class GitBranchesResponse(BaseModel):
    branches: List[GitBranchInfo]
    repo: str
    success: bool
    error: Optional[str] = None


def _parse_git_repo(git_repo: str) -> str:
    """Normalize git repo URL and return the actual URL for cloning."""
    repo = git_repo.strip()
    return repo


def _is_git_available() -> bool:
    """Check if git is available on the system."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _list_git_branches(git_repo: str) -> GitBranchesResponse:
    """List all branches from a remote git repository."""
    repo = _parse_git_repo(git_repo)

    if not repo:
        return GitBranchesResponse(
            branches=[],
            repo=git_repo,
            success=False,
            error="Git repository URL is required",
        )

    if not _is_git_available():
        return GitBranchesResponse(
            branches=[],
            repo=git_repo,
            success=False,
            error="Git is not installed on the server",
        )

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="shipsmith-git-")

        result = subprocess.run(
            ["git", "ls-remote", "--heads", repo],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return GitBranchesResponse(
                branches=[],
                repo=git_repo,
                success=False,
                error=result.stderr.strip() or "Failed to list branches",
            )

        branches = []
        default_branch = None
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

        for line in lines:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                ref = parts[1]
                if ref.startswith("refs/heads/"):
                    branch_name = ref[len("refs/heads/") :]
                    branches.append(GitBranchInfo(name=branch_name))

        if not branches:
            return GitBranchesResponse(
                branches=[],
                repo=git_repo,
                success=False,
                error="No branches found in the repository",
            )

        try:
            result = subprocess.run(
                ["git", "ls-remote", "--symref", repo, "HEAD"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if "ref:" in line:
                        match = re.search(r"ref:\s*refs/heads/([^\s]+)", line)
                        if match:
                            default_branch = match.group(1)
                            break
        except Exception:
            pass

        if not default_branch:
            for name in ["main", "master"]:
                if any(b.name == name for b in branches):
                    default_branch = name
                    break
            if not default_branch and branches:
                default_branch = branches[0].name

        for branch in branches:
            if branch.name == default_branch:
                branch.is_default = True

        branches = sorted(
            branches,
            key=lambda b: (0 if b.is_default else 1, b.name.lower()),
        )

        return GitBranchesResponse(
            branches=branches,
            repo=git_repo,
            success=True,
            error=None,
        )

    except subprocess.TimeoutExpired:
        return GitBranchesResponse(
            branches=[],
            repo=git_repo,
            success=False,
            error="Operation timed out. Please try again.",
        )
    except Exception as e:
        return GitBranchesResponse(
            branches=[],
            repo=git_repo,
            success=False,
            error=str(e) or "Failed to list branches",
        )
    finally:
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/git-branches", response_model=GitBranchesResponse)
async def list_git_branches(
    request: GitBranchesRequest,
    current_user: dict = Depends(get_current_user),
):
    return _list_git_branches(request.git_repo)
