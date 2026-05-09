"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("git_repo", sa.Text(), nullable=False),
        sa.Column("git_branch", sa.String(length=64), nullable=False, server_default="main"),
        sa.Column("deploy_workdir", sa.Text(), nullable=False),
        sa.Column("compose_file", sa.String(length=256), nullable=False, server_default="docker-compose.yml"),
        sa.Column("compose_service", sa.String(length=128), nullable=False, server_default="app"),
        sa.Column("deploy_strategy", sa.String(length=32), nullable=False, server_default="compose-build"),
        sa.Column("healthcheck_url", sa.Text(), nullable=True),
        sa.Column("healthcheck_timeout_seconds", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("flags_file_path", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("agent_token_hash", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.sql.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "key", name="uq_feature_flags_project_key"),
    )
    op.create_index("ix_feature_flags_project_id", "feature_flags", ["project_id"])

    op.create_table(
        "flag_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("flag_key", sa.String(length=64), nullable=False),
        sa.Column("old_enabled", sa.Boolean(), nullable=True),
        sa.Column("new_enabled", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flag_audits_project_id", "flag_audits", ["project_id"])

    op.create_table(
        "heartbeats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_heartbeats_project_id", "heartbeats", ["project_id"])

    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("trigger_source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("commit_hash", sa.String(length=40), nullable=True),
        sa.Column("target_deployment_id", sa.Integer(), nullable=True),
        sa.Column("log_excerpt", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("triggered_by", sa.String(length=64), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_deployment_id"], ["deployments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])

    op.create_table(
        "deployment_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deployment_id", "seq", name="uq_deployment_logs_deployment_seq"),
    )
    op.create_index("ix_deployment_logs_deployment_id", "deployment_logs", ["deployment_id"])

    op.create_table(
        "project_status",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("agent_last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("health_status", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("current_commit_hash", sa.String(length=40), nullable=True),
        sa.Column("last_deployment_id", sa.Integer(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["last_deployment_id"], ["deployments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id"),
    )


def downgrade() -> None:
    op.drop_table("project_status")
    op.drop_index("ix_deployment_logs_deployment_id", table_name="deployment_logs")
    op.drop_table("deployment_logs")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_table("deployments")
    op.drop_index("ix_heartbeats_project_id", table_name="heartbeats")
    op.drop_table("heartbeats")
    op.drop_index("ix_flag_audits_project_id", table_name="flag_audits")
    op.drop_table("flag_audits")
    op.drop_index("ix_feature_flags_project_id", table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_table("projects")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
