from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field

from .enums import (
    TaskKind,
    DeployStatus,
    HealthStatus,
    DeployStrategy,
    ErrorCode,
)


class TaskPhase(str, Enum):
    GIT_FETCH = "git_fetch"
    GIT_CHECKOUT = "git_checkout"
    GIT_RESET = "git_reset"
    PRE_DEPLOY = "pre_deploy"
    DOCKER_BUILD = "docker_build"
    DOCKER_PULL = "docker_pull"
    DOCKER_UP = "docker_up"
    POST_DEPLOY = "post_deploy"
    HEALTH_CHECK = "health_check"


class AgentTask(BaseModel):
    id: int
    project_id: int
    kind: TaskKind
    commit_hash: Optional[str] = None
    target_commit_hash: Optional[str] = None
    deploy_strategy: DeployStrategy
    created_at: datetime


class AgentTaskResponse(BaseModel):
    task: Optional[AgentTask] = None
    message: str = "No pending tasks"


class TaskStartRequest(BaseModel):
    agent_id: str = Field(..., description="执行任务的 Agent ID")
    started_at: datetime = Field(default_factory=datetime.utcnow)


class TaskLogRequest(BaseModel):
    phase: TaskPhase = Field(..., description="当前执行阶段")
    seq: int = Field(..., ge=0, description="日志序号，用于增量追加")
    content: str = Field(..., description="日志内容")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TaskFinishRequest(BaseModel):
    status: DeployStatus = Field(..., description="最终状态：success 或 failed")
    commit_hash: Optional[str] = Field(default=None, description="实际部署的 commit hash")
    error_code: Optional[ErrorCode] = Field(default=None, description="失败时的错误码")
    error_message: Optional[str] = Field(default=None, description="失败详情")
    finished_at: datetime = Field(default_factory=datetime.utcnow)


class FlagSyncRequest(BaseModel):
    current_version: int = Field(..., ge=0, description="Agent 当前本地 flags 版本号")


class FlagSyncResponse(BaseModel):
    version: int = Field(..., description="最新 flags 版本号")
    flags: Optional[Dict[str, bool]] = Field(default=None, description="flags 字典，无变更时为 None")
    changed: bool = Field(..., description="是否有变更")


class SystemMetrics(BaseModel):
    cpu_percent: float = Field(..., ge=0, le=100)
    mem_used_mb: int = Field(..., ge=0)
    mem_total_mb: int = Field(..., ge=1)
    disk_used_percent: float = Field(..., ge=0, le=100)


class ContainerStatus(BaseModel):
    service: str
    status: str
    image: Optional[str] = None
    ports: List[str] = Field(default_factory=list)
    uptime_seconds: int = Field(default=0)
    restart_count: int = Field(default=0)


class AppHealth(BaseModel):
    status: HealthStatus
    response_ms: Optional[int] = None
    http_status: Optional[int] = None
    version: Optional[str] = None


class HeartbeatPayload(BaseModel):
    project_id: int
    agent_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    system: SystemMetrics
    containers: List[ContainerStatus] = Field(default_factory=list)
    app_health: AppHealth


class HeartbeatResponse(BaseModel):
    received: bool = True
    server_time: datetime = Field(default_factory=datetime.utcnow)
