"""add diagnostic snapshots

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa


revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deployment_id", sa.Integer(), sa.ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("trigger", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_diagnostic_snapshots_project_id", "diagnostic_snapshots", ["project_id"])
    op.create_index("ix_diagnostic_snapshots_deployment_id", "diagnostic_snapshots", ["deployment_id"])
    op.create_index("ix_diagnostic_snapshots_created_at", "diagnostic_snapshots", ["created_at"])
    op.create_index(
        "ix_diagnostic_snapshots_project_created",
        "diagnostic_snapshots",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_diagnostic_snapshots_project_created", table_name="diagnostic_snapshots")
    op.drop_index("ix_diagnostic_snapshots_created_at", table_name="diagnostic_snapshots")
    op.drop_index("ix_diagnostic_snapshots_deployment_id", table_name="diagnostic_snapshots")
    op.drop_index("ix_diagnostic_snapshots_project_id", table_name="diagnostic_snapshots")
    op.drop_table("diagnostic_snapshots")
