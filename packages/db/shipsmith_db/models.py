from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    JSON,
    ForeignKey,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from .engine import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    environment = Column(String(16), nullable=True, index=True)
    git_repo = Column(Text, nullable=False)
    git_branch = Column(String(64), nullable=False, default="main")
    git_credential_type = Column(String(32), nullable=False, default="none")
    git_credential_username = Column(String(256))
    git_credential_token_encrypted = Column(Text)
    git_credential_ssh_private_key_encrypted = Column(Text)
    git_credential_ssh_known_hosts = Column(Text)
    deploy_workdir = Column(Text, nullable=False)
    compose_file = Column(String(256), nullable=False, default="docker-compose.yml")
    compose_service = Column(String(128), nullable=False, default="app")
    deploy_strategy = Column(String(32), nullable=False, default="compose-build")
    healthcheck_url = Column(Text)
    healthcheck_timeout_seconds = Column(Integer, nullable=False, default=10)
    healthcheck_expected_status = Column(Integer, nullable=False, default=200)
    flags_file_path = Column(Text, nullable=False)
    pre_deploy_command = Column(Text)
    post_deploy_command = Column(Text)
    migration_service = Column(String(128), nullable=False, default="")
    migration_command = Column(Text)
    migration_timeout_seconds = Column(Integer, nullable=False, default=600)
    migration_no_deps = Column(Boolean, nullable=False, default=True)
    compose_profiles = Column(JSON, nullable=False, default=list)
    build_timeout_seconds = Column(Integer, nullable=False, default=1800)
    pull_timeout_seconds = Column(Integer, nullable=False, default=900)
    build_no_cache = Column(Boolean, nullable=False, default=False)
    service_scope = Column(String(16), nullable=False, default="app")
    app_services = Column(JSON, nullable=False, default=list)
    agent_id = Column(String(64), nullable=False)
    agent_token_hash = Column(String(256), nullable=False)
    webhook_secret = Column(String(256))
    webhook_endpoint_id = Column(String(64), unique=True)
    notes = Column(Text)
    release_notes_hint = Column(Text)
    troubleshooting_hint = Column(Text)
    admin_url = Column(Text)
    metrics_url = Column(Text)
    logs_url = Column(Text)
    ssh_hint = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")
    targets = relationship("ProjectTarget", back_populates="project", cascade="all, delete-orphan")
    flags = relationship("FeatureFlag", back_populates="project", cascade="all, delete-orphan")
    flag_audits = relationship("FlagAudit", back_populates="project", cascade="all, delete-orphan")
    status = relationship("ProjectStatus", back_populates="project", uselist=False, cascade="all, delete-orphan")
    heartbeats = relationship("Heartbeat", back_populates="project", cascade="all, delete-orphan")
    webhook_deliveries = relationship("WebhookDelivery", back_populates="project", cascade="all, delete-orphan")


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    deploy_mode = Column(String(32), nullable=False, default="all-at-once")
    trigger_source = Column(String(16), nullable=False, default="manual")
    commit_hash = Column(String(40))
    previous_commit_hash = Column(String(64))
    image_snapshot = Column(JSON)
    health_result = Column(JSON)
    target_deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="SET NULL"))
    log_excerpt = Column(Text)
    error_code = Column(String(64))
    failure_phase = Column(String(32))
    webhook_delivery_id = Column(String(128), index=True)
    triggered_by = Column(String(64))
    queued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    lease_expires_at = Column(DateTime)
    last_heartbeat_at = Column(DateTime)

    project = relationship("Project", back_populates="deployments")
    targets = relationship("DeploymentTarget", back_populates="deployment", cascade="all, delete-orphan")
    logs = relationship("DeploymentLog", back_populates="deployment", cascade="all, delete-orphan")


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    deployment_target_id = Column(Integer, ForeignKey("deployment_targets.id", ondelete="SET NULL"), nullable=True, index=True)
    seq = Column(Integer, nullable=False)
    phase = Column(String(32))
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    deployment = relationship("Deployment", back_populates="logs")
    deployment_target = relationship("DeploymentTarget", back_populates="logs")

    __table_args__ = (
        UniqueConstraint("deployment_target_id", "seq", name="uq_deployment_logs_target_seq"),
    )


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
    description = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(String(64))
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    archived = Column(Boolean, nullable=False, default=False)
    archived_at = Column(DateTime)
    archived_by = Column(String(64))

    project = relationship("Project", back_populates="flags")

    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_feature_flags_project_key"),
    )


class FlagAudit(Base):
    __tablename__ = "flag_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    flag_key = Column(String(64), nullable=False)
    old_enabled = Column(Boolean)
    new_enabled = Column(Boolean, nullable=False)
    changed_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="flag_audits")


class ProjectStatus(Base):
    __tablename__ = "project_status"

    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    agent_first_seen_at = Column(DateTime)
    agent_last_seen_at = Column(DateTime)
    health_status = Column(String(16), nullable=False, default="unknown")
    current_commit_hash = Column(String(40))
    last_deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="SET NULL"))
    intentionally_stopped = Column(Boolean, nullable=False, default=False)
    snapshot = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="status")


class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="heartbeats")


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    source = Column(String(32), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project", back_populates="webhook_deliveries")

    __table_args__ = (
        UniqueConstraint("project_id", "delivery_id", name="uq_webhook_deliveries_project_delivery"),
    )


class ProjectAudit(Base):
    __tablename__ = "project_audits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(32), nullable=False, default="update")
    changed_by = Column(String(64))
    old_values = Column(JSON, nullable=False, default=dict)
    new_values = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project")


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    channel_type = Column(String(32), nullable=False)
    config = Column(JSON, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")
    deliveries = relationship("NotificationDelivery", back_populates="channel", cascade="all, delete-orphan")


class ProjectNotificationSetting(Base):
    __tablename__ = "project_notification_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    channel_ids = Column(JSON, nullable=False, default=list)
    cooldown_seconds = Column(Integer, nullable=False, default=600)
    send_recovery = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")

    __table_args__ = (
        UniqueConstraint("project_id", "event_type", name="uq_project_notification_settings_project_event"),
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    fingerprint = Column(String(256), index=True)
    is_recovery = Column(Boolean, nullable=False, default=False)
    is_suppressed = Column(Boolean, nullable=False, default=False)
    status = Column(String(32), nullable=False, default="queued")
    error_message = Column(Text)
    payload = Column(JSON, nullable=False, default=dict)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    channel = relationship("NotificationChannel", back_populates="deliveries")
    project = relationship("Project")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_type = Column(String(64), nullable=False, index=True)
    fingerprint = Column(String(256), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="open", index=True)
    title = Column(String(256), nullable=False)
    message = Column(Text)
    alert_metadata = Column(JSON, nullable=False, default=dict)
    acknowledged_by = Column(String(64))
    acknowledged_at = Column(DateTime)
    resolved_by = Column(String(64))
    resolved_at = Column(DateTime)
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project")

    __table_args__ = (
        Index(
            "uq_alerts_project_fingerprint_active",
            "project_id",
            "fingerprint",
            unique=True,
            postgresql_where=text("status IN ('open', 'acknowledged')"),
            sqlite_where=text("status IN ('open', 'acknowledged')"),
        ),
    )


class AgentPrecheck(Base):
    __tablename__ = "agent_prechecks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False)
    overall_status = Column(String(16), nullable=False)
    summary = Column(JSON, nullable=False, default=dict)
    result_json = Column(JSON, nullable=False, default=dict)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("Project")


class ProjectTarget(Base):
    __tablename__ = "project_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False, default="default")
    role = Column(String(32), nullable=False, default="primary")
    enabled = Column(Boolean, nullable=False, default=True)
    order_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="targets")
    deployment_targets = relationship("DeploymentTarget", back_populates="project_target", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "agent_id", name="uq_project_targets_project_agent"),
    )


class DeploymentTarget(Base):
    __tablename__ = "deployment_targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(Integer, ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False, index=True)
    project_target_id = Column(Integer, ForeignKey("project_targets.id", ondelete="SET NULL"), nullable=True)
    agent_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    commit_hash = Column(String(40))
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_code = Column(String(64))
    error_message = Column(Text)
    target_commit_hash = Column(String(64))
    previous_commit_hash = Column(String(64))
    image_snapshot = Column(JSON)
    health_result = Column(JSON)
    failure_phase = Column(String(32))
    lease_expires_at = Column(DateTime)
    last_heartbeat_at = Column(DateTime)

    deployment = relationship("Deployment", back_populates="targets")
    project_target = relationship("ProjectTarget", back_populates="deployment_targets")
    logs = relationship("DeploymentLog", back_populates="deployment_target", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("deployment_id", "project_target_id", name="uq_deployment_targets_deployment_project_target"),
    )


class DiagnosticSnapshot(Base):
    """A bounded capture of container state and runtime logs.

    Created when an operator asks for logs, when a deploy fails its health
    check, or when an application flips from healthy to unhealthy.
    """

    __tablename__ = "diagnostic_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deployment_id = Column(
        Integer, ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id = Column(String(64))
    trigger = Column(String(32), nullable=False, default="manual")
    reason = Column(String(200))
    content = Column(Text, nullable=False, default="")
    byte_size = Column(Integer, nullable=False, default=0)
    truncated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_diagnostic_snapshots_project_created", "project_id", "created_at"),
    )
