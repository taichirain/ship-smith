from datetime import datetime
from typing import Optional, List, Dict, Any, Literal, Union
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


EnvironmentType = Literal["production", "staging", "development", "testing", "other"]
GitCredentialType = Literal["none", "http_token", "ssh_key"]


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=128)
    environment: Optional[EnvironmentType] = None
    git_repo: str
    git_branch: str = Field(default="main", max_length=64)
    git_credential_type: GitCredentialType = "none"
    git_credential_username: Optional[str] = Field(default=None, max_length=256)
    git_credential_token: Optional[str] = None
    git_credential_ssh_private_key: Optional[str] = None
    git_credential_ssh_known_hosts: Optional[str] = None
    deploy_workdir: str
    compose_file: str = Field(default="docker-compose.yml", max_length=256)
    compose_service: str = Field(default="app", max_length=128)
    deploy_strategy: str = Field(default="compose-build", max_length=32)
    healthcheck_url: Optional[str] = None
    healthcheck_timeout_seconds: int = Field(default=10, ge=1, le=300)
    healthcheck_expected_status: int = Field(default=200, ge=100, le=599)
    flags_file_path: str
    pre_deploy_command: Optional[str] = None
    post_deploy_command: Optional[str] = None
    migration_service: str = Field(default="", max_length=128)
    migration_command: Optional[str] = None
    migration_timeout_seconds: int = Field(default=600, ge=1, le=7200)
    migration_no_deps: bool = True
    migration_phase: str = Field(default="pre", max_length=8)
    migration_backup_service: str = Field(default="", max_length=128)
    migration_backup_command: Optional[str] = None
    compose_profiles: List[str] = Field(default_factory=list)
    build_timeout_seconds: int = Field(default=1800, ge=60, le=10800)
    pull_timeout_seconds: int = Field(default=900, ge=60, le=7200)
    build_no_cache: bool = False
    service_scope: str = Field(default="app", max_length=16)
    release_tag_env: str = Field(default="", max_length=64)
    app_services: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    release_notes_hint: Optional[str] = None
    troubleshooting_hint: Optional[str] = None
    admin_url: Optional[str] = None
    metrics_url: Optional[str] = None
    logs_url: Optional[str] = None
    ssh_hint: Optional[str] = None


class ProjectCreate(ProjectBase):
    @field_validator("deploy_workdir", "flags_file_path")
    @classmethod
    def paths_must_be_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("must be an absolute path")
        return value

    @field_validator("deploy_workdir")
    @classmethod
    def workdir_must_be_dedicated(cls, value: str) -> str:
        normalized = value.rstrip("/") or "/"
        forbidden = {"/", "/home", "/root", "/opt", "/usr", "/var", "/etc", "/tmp", "/srv"}
        if normalized in forbidden:
            raise ValueError("deploy_workdir is too broad; choose a dedicated project directory")
        return value

    @field_validator("deploy_strategy")
    @classmethod
    def strategy_must_be_supported(cls, value: str) -> str:
        if value not in {"compose-build", "compose-pull"}:
            raise ValueError("must be compose-build or compose-pull")
        return value

    @field_validator("migration_command")
    @classmethod
    def migration_command_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            return None
        return value

    @field_validator("service_scope")
    @classmethod
    def service_scope_must_be_valid(cls, value: str) -> str:
        if value not in {"app", "all"}:
            raise ValueError("service_scope must be 'app' or 'all'")
        return value

    @field_validator("migration_phase")
    @classmethod
    def migration_phase_must_be_valid(cls, value: str) -> str:
        if value not in {"pre", "post"}:
            raise ValueError("migration_phase must be 'pre' or 'post'")
        return value

    @field_validator("app_services")
    @classmethod
    def app_services_must_be_valid(cls, value: List[str]) -> List[str]:
        import re

        if len(value) != len(set(value)) or any(
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", service) for service in value
        ):
            raise ValueError("app_services must be unique Compose service names")
        return value

    @field_validator("compose_profiles")
    @classmethod
    def compose_profiles_must_be_valid(cls, value: List[str]) -> List[str]:
        import re

        for profile in value:
            if not re.match(r"^[A-Za-z0-9._-]+$", profile):
                raise ValueError(f"invalid compose profile: {profile}")
        return value


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    environment: Optional[EnvironmentType] = None
    git_repo: Optional[str] = None
    git_branch: Optional[str] = Field(default=None, max_length=64)
    git_credential_type: Optional[GitCredentialType] = None
    git_credential_username: Optional[str] = Field(default=None, max_length=256)
    git_credential_token: Optional[str] = None
    git_credential_ssh_private_key: Optional[str] = None
    git_credential_ssh_known_hosts: Optional[str] = None
    deploy_workdir: Optional[str] = None
    compose_file: Optional[str] = Field(default=None, max_length=256)
    compose_service: Optional[str] = Field(default=None, max_length=128)
    deploy_strategy: Optional[str] = Field(default=None, max_length=32)
    healthcheck_url: Optional[str] = None
    healthcheck_timeout_seconds: Optional[int] = Field(default=None, ge=1, le=300)
    healthcheck_expected_status: Optional[int] = Field(default=None, ge=100, le=599)
    flags_file_path: Optional[str] = None
    pre_deploy_command: Optional[str] = None
    post_deploy_command: Optional[str] = None
    migration_service: Optional[str] = Field(default=None, max_length=128)
    migration_command: Optional[str] = None
    migration_timeout_seconds: Optional[int] = Field(default=None, ge=1, le=7200)
    migration_no_deps: Optional[bool] = None
    migration_phase: Optional[str] = Field(default=None, max_length=8)
    migration_backup_service: Optional[str] = Field(default=None, max_length=128)
    migration_backup_command: Optional[str] = None
    compose_profiles: Optional[List[str]] = None
    build_timeout_seconds: Optional[int] = Field(default=None, ge=60, le=10800)
    pull_timeout_seconds: Optional[int] = Field(default=None, ge=60, le=7200)
    build_no_cache: Optional[bool] = None
    service_scope: Optional[str] = Field(default=None, max_length=16)
    release_tag_env: Optional[str] = Field(default=None, max_length=64)
    app_services: Optional[List[str]] = None
    webhook_secret: Optional[str] = Field(default=None, max_length=256)
    notes: Optional[str] = None
    release_notes_hint: Optional[str] = None
    troubleshooting_hint: Optional[str] = None
    admin_url: Optional[str] = None
    metrics_url: Optional[str] = None
    logs_url: Optional[str] = None
    ssh_hint: Optional[str] = None

    @field_validator("deploy_workdir", "flags_file_path")
    @classmethod
    def optional_paths_must_be_absolute(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.startswith("/"):
            raise ValueError("must be an absolute path")
        return value

    @field_validator("deploy_workdir")
    @classmethod
    def optional_workdir_must_be_dedicated(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.rstrip("/") or "/"
        forbidden = {"/", "/home", "/root", "/opt", "/usr", "/var", "/etc", "/tmp", "/srv"}
        if normalized in forbidden:
            raise ValueError("deploy_workdir is too broad; choose a dedicated project directory")
        return value

    @field_validator("deploy_strategy")
    @classmethod
    def optional_strategy_must_be_supported(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"compose-build", "compose-pull"}:
            raise ValueError("must be compose-build or compose-pull")
        return value

    @field_validator("migration_command")
    @classmethod
    def optional_migration_command_must_not_be_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            return None
        return value

    @field_validator("service_scope")
    @classmethod
    def optional_service_scope_must_be_valid(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"app", "all"}:
            raise ValueError("service_scope must be 'app' or 'all'")
        return value

    @field_validator("migration_phase")
    @classmethod
    def optional_migration_phase_must_be_valid(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"pre", "post"}:
            raise ValueError("migration_phase must be 'pre' or 'post'")
        return value

    @field_validator("app_services")
    @classmethod
    def optional_app_services_must_be_valid(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        if value is None:
            return value
        return ProjectCreate.app_services_must_be_valid(value)

    @field_validator("compose_profiles")
    @classmethod
    def optional_compose_profiles_must_be_valid(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        import re

        if value is None:
            return value
        for profile in value:
            if not re.match(r"^[A-Za-z0-9._-]+$", profile):
                raise ValueError(f"invalid compose profile: {profile}")
        return value


class ProjectTargetBase(BaseModel):
    name: str = Field(default="default", max_length=128)
    role: str = Field(default="primary", max_length=32)
    enabled: bool = True
    order_index: int = 0


class ProjectTargetCreate(ProjectTargetBase):
    agent_id: str = Field(..., max_length=64)


class ProjectTargetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    role: Optional[str] = Field(default=None, max_length=32)
    enabled: Optional[bool] = None
    order_index: Optional[int] = None


class ProjectTargetResponse(ProjectTargetBase):
    id: int
    project_id: int
    agent_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectResponse(ProjectBase):
    id: int
    agent_id: str
    agent_token: Optional[str] = Field(default=None, description="仅在创建时返回一次")
    webhook_secret: Optional[str] = Field(default=None, description="仅在创建/编辑时返回")
    git_credential_configured: bool = False
    webhook_endpoint_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectWithStatusResponse(ProjectResponse):
    health_status: Optional[str] = None
    agent_last_seen_at: Optional[datetime] = None
    current_commit_hash: Optional[str] = None


class RotateAgentTokenResponse(BaseModel):
    agent_id: str
    agent_token: str


class ProjectStatusDetailResponse(BaseModel):
    project_id: int
    agent_last_seen_at: Optional[datetime] = None
    health_status: str
    intentionally_stopped: bool = False
    current_commit_hash: Optional[str] = None
    last_deployment_id: Optional[int] = None
    updated_at: datetime
    cpu_percent: Optional[float] = None
    mem_used_mb: Optional[int] = None
    mem_total_mb: Optional[int] = None
    disk_used_percent: Optional[float] = None
    containers: Optional[List[Dict[str, Any]]] = None
    app_health: Optional[Dict[str, Any]] = None
    agent_version: Optional[str] = None
    agent_version_outdated: Optional[bool] = None
    runtime: Optional[Dict[str, Any]] = None


class ProjectListResponse(BaseModel):
    id: int
    name: str
    environment: Optional[EnvironmentType] = None
    git_repo: str
    git_branch: str
    deploy_workdir: str
    deploy_strategy: str
    health_status: str = Field(default="unknown")
    agent_last_seen_at: Optional[datetime] = None
    current_commit_hash: Optional[str] = None
    last_deployment_status: Optional[str] = None
    last_deployment_at: Optional[datetime] = None
    webhook_endpoint_id: Optional[str] = None
    agent_version: Optional[str] = None
    agent_version_outdated: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeploymentBase(BaseModel):
    kind: str = Field(default="deploy")
    commit_hash: Optional[str] = None


class DeploymentCreate(DeploymentBase):
    trigger_source: str = Field(default="manual")


class DeploymentResponse(BaseModel):
    id: int
    project_id: int
    kind: str
    status: str
    deploy_mode: str = "all-at-once"
    trigger_source: str
    commit_hash: Optional[str] = None
    previous_commit_hash: Optional[str] = None
    image_snapshot: Optional[Dict[str, Any]] = None
    health_result: Optional[Dict[str, Any]] = None
    target_deployment_id: Optional[int] = None
    log_excerpt: Optional[str] = None
    error_code: Optional[str] = None
    triggered_by: Optional[str] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    failure_phase: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    requested_services: Optional[List[str]] = None
    effective_services: Optional[List[str]] = None
    effective_service_scope: Optional[str] = None

    class Config:
        from_attributes = True


class DeploymentTargetResponse(BaseModel):
    id: int
    deployment_id: int
    project_target_id: Optional[int] = None
    agent_id: str
    status: str
    commit_hash: Optional[str] = None
    target_commit_hash: Optional[str] = None
    previous_commit_hash: Optional[str] = None
    image_snapshot: Optional[Dict[str, Any]] = None
    health_result: Optional[Dict[str, Any]] = None
    failure_phase: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeployRequest(BaseModel):
    commit_hash: Optional[str] = None
    trigger_source: str = Field(default="manual")
    deploy_mode: str = Field(default="all-at-once")
    services: Optional[List[str]] = None


class RollbackRequest(BaseModel):
    target_deployment_id: int


class ServiceOperationRequest(BaseModel):
    services: Optional[List[str]] = None


class DeploymentLogResponse(BaseModel):
    id: int
    deployment_id: int
    deployment_target_id: Optional[int] = None
    seq: int
    phase: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureFlagBase(BaseModel):
    key: str = Field(..., max_length=64)
    enabled: bool = Field(default=False)
    description: Optional[str] = None


class FeatureFlagCreate(FeatureFlagBase):
    pass


class FeatureFlagPatch(BaseModel):
    enabled: Optional[bool] = None
    description: Optional[str] = None


class FeatureFlagResponse(FeatureFlagBase):
    id: int
    project_id: int
    version: int
    updated_by: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class FlagAuditResponse(BaseModel):
    id: int
    project_id: int
    flag_key: str
    old_enabled: Optional[bool] = None
    new_enabled: bool
    changed_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectStatusResponse(BaseModel):
    project_id: int
    agent_last_seen_at: Optional[datetime] = None
    health_status: str
    current_commit_hash: Optional[str] = None
    last_deployment_id: Optional[int] = None
    updated_at: datetime

    class Config:
        from_attributes = True


HealthStatus = Literal["healthy", "degraded", "unhealthy", "unknown"]
DeploymentStatus = Literal["queued", "running", "success", "failed"]
AnomalyType = Literal["agent_offline", "health_unhealthy", "health_degraded", "last_deploy_failed"]
EventCategory = Literal["deployment", "rollback", "flag_audit", "webhook", "config", "agent", "operation"]
TimelineEventType = Literal[
    "deployment_queued",
    "deployment_running",
    "deployment_success",
    "deployment_failed",
    "rollback_queued",
    "rollback_running",
    "rollback_success",
    "rollback_failed",
    "flag_created",
    "flag_updated",
    "flag_archived",
    "flag_unarchived",
    "config_updated",
    "webhook_accepted",
    "webhook_ignored",
    "agent_offline",
    "agent_recovered",
    "operation_queued",
    "operation_running",
    "operation_success",
    "operation_failed",
]


class DashboardSummary(BaseModel):
    total_projects: int
    healthy_projects: int
    degraded_projects: int
    unhealthy_projects: int
    offline_projects: int
    stopped_projects: int
    last_24h_deployments_success: int
    last_24h_deployments_failed: int


class AnomalyProject(BaseModel):
    project_id: int
    project_name: str
    anomaly_types: List[AnomalyType]
    health_status: Optional[str] = None
    agent_last_seen_at: Optional[datetime] = None
    last_deployment_status: Optional[str] = None
    last_deployment_id: Optional[int] = None
    last_deployment_at: Optional[datetime] = None


class ChangeEvent(BaseModel):
    event_category: EventCategory
    event_type: str
    occurred_at: datetime
    project_id: int
    project_name: str
    title: str
    summary: Optional[str] = None
    actor: Optional[str] = None
    deployment_id: Optional[int] = None
    flag_key: Optional[str] = None


class DashboardSummaryResponse(BaseModel):
    summary: DashboardSummary
    anomaly_projects: List[AnomalyProject]
    recent_changes: List[ChangeEvent]


class TimelineEvent(BaseModel):
    id: str
    type: TimelineEventType
    occurred_at: datetime
    title: str
    summary: Optional[str] = None
    actor: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    events: List[TimelineEvent]
    total: int


ChannelType = Literal["webhook", "feishu", "slack"]
AlertStatus = Literal["open", "acknowledged", "resolved"]
AlertType = Literal["agent_offline", "deployment_failed", "health_unhealthy"]
NotificationEventType = Literal[
    "deployment_success",
    "deployment_failed",
    "agent_offline",
    "health_degraded",
    "health_unhealthy",
    "health_recovered",
]


class WebhookConfig(BaseModel):
    url: str
    method: str = Field(default="POST")
    headers: Dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=10, ge=1, le=120)


class FeishuConfig(BaseModel):
    webhook_url: str
    timeout_seconds: int = Field(default=10, ge=1, le=120)


class SlackConfig(BaseModel):
    webhook_url: str
    timeout_seconds: int = Field(default=10, ge=1, le=120)


ChannelConfig = Union[WebhookConfig, FeishuConfig, SlackConfig]


class NotificationChannelBase(BaseModel):
    name: str = Field(..., max_length=128)
    channel_type: ChannelType
    is_active: bool = True


class NotificationChannelCreate(NotificationChannelBase):
    config: ChannelConfig


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=128)
    is_active: Optional[bool] = None
    config: Optional[ChannelConfig] = None


class NotificationChannelResponse(NotificationChannelBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectNotificationSettingBase(BaseModel):
    event_type: NotificationEventType
    enabled: bool = True
    channel_ids: List[int] = Field(default_factory=list)
    cooldown_seconds: int = Field(default=600, ge=0, le=86400)
    send_recovery: bool = True


class ProjectNotificationSettingUpdate(BaseModel):
    enabled: Optional[bool] = None
    channel_ids: Optional[List[int]] = None
    cooldown_seconds: Optional[int] = Field(default=None, ge=0, le=86400)
    send_recovery: Optional[bool] = None


class ProjectNotificationSettingResponse(ProjectNotificationSettingBase):
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationDeliveryResponse(BaseModel):
    id: int
    channel_id: int
    project_id: int
    event_type: str
    fingerprint: Optional[str] = None
    is_recovery: bool = False
    is_suppressed: bool = False
    status: str
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    channel_id: int
    event_type: Optional[NotificationEventType] = None


class TestNotificationResponse(BaseModel):
    success: bool
    message: str
    status_code: Optional[int] = None


class AlertResponse(BaseModel):
    id: int
    project_id: int
    alert_type: AlertType
    fingerprint: str
    status: AlertStatus
    title: str
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    project_name: Optional[str] = None

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    open_count: int
    acknowledged_count: int
    resolved_count: int


class HealthHistoryRecord(BaseModel):
    timestamp: datetime
    health_status: str
    response_ms: Optional[int] = None
    heartbeat_present: bool = True


class DeploymentMarker(BaseModel):
    timestamp: datetime
    deployment_id: int
    status: str
    kind: str
    commit_hash: Optional[str] = None


class HealthHistoryResponse(BaseModel):
    records: List[HealthHistoryRecord]
    deployment_markers: List[DeploymentMarker]


class DeployCommandGenerateRequest(BaseModel):
    user_goal: Optional[str] = Field(default=None, max_length=500)
    preferred_shell: Optional[str] = Field(default=None, max_length=64)
    extra_context: Optional[str] = Field(default=None, max_length=4000)


class DeployCommandPlan(BaseModel):
    title: str
    command: str
    purpose: str


class DeployCommandGenerateResponse(BaseModel):
    project_id: int
    source_files: List[str]
    system_summary: Dict[str, Any]
    assumptions: List[str]
    prechecks: List[str]
    commands: List[DeployCommandPlan]
    verification: List[str]
    explanation: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_duration_ms: Optional[int] = None


class InstallMode(str, Enum):
    STANDARD = "standard"
    DRY_RUN = "dry-run"


class TargetPlatform(str, Enum):
    LINUX_SYSTEMD = "linux-systemd"
    LINUX_DOCKER = "linux-docker"
    MANUAL = "manual"


class InstallCommandRequest(BaseModel):
    install_mode: InstallMode = Field(default=InstallMode.STANDARD)
    target_platform: TargetPlatform = Field(default=TargetPlatform.LINUX_SYSTEMD)
    core_url: Optional[str] = Field(default=None, description="Optional override for core URL")
    workdir: Optional[str] = Field(default=None, description="Optional override for workdir")


class InstallCommandResponse(BaseModel):
    project_id: int
    install_mode: str
    target_platform: str
    command: str
    expires_at: Optional[datetime] = None
    manual_install_url: Optional[str] = None
    notes: List[str]
    agent_id: str
    core_url: str
    workdir: str


class AgentOnboardingStatus(str, Enum):
    WAITING = "waiting"
    ONLINE = "online"
    FAILED = "failed"
    EXPIRED = "expired"


class OnboardingStatusResponse(BaseModel):
    project_id: int
    agent_id: str
    core_url: str
    workdir: str
    status: AgentOnboardingStatus
    agent_first_seen_at: Optional[datetime] = None
    agent_last_seen_at: Optional[datetime] = None
    health_status: Optional[str] = None
    install_command: Optional[str] = None
    install_command_expires_at: Optional[datetime] = None
    manual_steps_available: bool = True
    troubleshooting_hints: List[str] = []


class DiagnosticSnapshotSummary(BaseModel):
    id: int
    project_id: int
    deployment_id: Optional[int] = None
    trigger: str = "manual"
    reason: Optional[str] = None
    byte_size: int = 0
    truncated: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class DiagnosticSnapshotDetail(DiagnosticSnapshotSummary):
    content: str = ""


class DiagnosticSnapshotIngest(BaseModel):
    deployment_id: Optional[int] = None
    trigger: str = Field(default="manual")
    reason: Optional[str] = None
    content: str = ""
    truncated: bool = False
