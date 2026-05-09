"""add_multi_deploy_targets

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="primary"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.sql.true()),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "agent_id", name="uq_project_targets_project_agent"),
    )
    op.create_index("ix_project_targets_project_id", "project_targets", ["project_id"])
    op.create_index("ix_project_targets_project_enabled_order", "project_targets", ["project_id", "enabled", "order_index"])

    op.create_table(
        "deployment_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("project_target_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("commit_hash", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_target_id"], ["project_targets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deployment_id", "project_target_id", name="uq_deployment_targets_deployment_project_target"),
    )
    op.create_index("ix_deployment_targets_deployment_id", "deployment_targets", ["deployment_id"])
    op.create_index("ix_deployment_targets_deployment_status", "deployment_targets", ["deployment_id", "status"])

    op.add_column(
        "deployment_logs",
        sa.Column(
            "deployment_target_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_index("ix_deployment_logs_deployment_target_id", "deployment_logs", ["deployment_target_id"])

    op.add_column(
        "deployments",
        sa.Column(
            "deploy_mode",
            sa.String(length=32),
            nullable=False,
            server_default="all-at-once",
        ),
    )

    conn = op.get_bind()
    now = datetime.utcnow()

    projects_table = table(
        "projects",
        column("id", sa.Integer),
        column("agent_id", sa.String),
        column("name", sa.String),
        column("created_at", sa.DateTime),
        column("updated_at", sa.DateTime),
    )

    project_targets_table = table(
        "project_targets",
        column("project_id", sa.Integer),
        column("agent_id", sa.String),
        column("name", sa.String),
        column("role", sa.String),
        column("enabled", sa.Boolean),
        column("order_index", sa.Integer),
        column("created_at", sa.DateTime),
        column("updated_at", sa.DateTime),
    )

    projects = conn.execute(
        sa.select(projects_table.c.id, projects_table.c.agent_id, projects_table.c.name)
    ).fetchall()

    for project in projects:
        conn.execute(
            project_targets_table.insert().values(
                project_id=project.id,
                agent_id=project.agent_id,
                name=f"{project.name}-default",
                role="primary",
                enabled=True,
                order_index=0,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_deployment_logs_deployment_target_id", table_name="deployment_logs")
    op.drop_column("deployment_logs", "deployment_target_id")

    op.drop_index("ix_deployment_targets_deployment_status", table_name="deployment_targets")
    op.drop_index("ix_deployment_targets_deployment_id", table_name="deployment_targets")
    op.drop_table("deployment_targets")

    op.drop_index("ix_project_targets_project_enabled_order", table_name="project_targets")
    op.drop_index("ix_project_targets_project_id", table_name="project_targets")
    op.drop_table("project_targets")

    op.drop_column("deployments", "deploy_mode")
