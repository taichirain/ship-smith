"""v030_schema_updates

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("webhook_secret", sa.String(length=256), nullable=True))
    op.add_column("projects", sa.Column("webhook_endpoint_id", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_projects_webhook_endpoint_id", "projects", ["webhook_endpoint_id"])

    op.add_column("deployments", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column("deployments", sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column("deployments", sa.Column("failure_phase", sa.String(length=32), nullable=True))
    op.add_column("deployments", sa.Column("webhook_delivery_id", sa.String(length=128), nullable=True))
    op.create_index("ix_deployments_webhook_delivery_id", "deployments", ["webhook_delivery_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("delivery_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "delivery_id", name="uq_webhook_deliveries_project_delivery"),
    )
    op.create_index("ix_webhook_deliveries_project_id", "webhook_deliveries", ["project_id"])
    op.create_index("ix_webhook_deliveries_delivery_id", "webhook_deliveries", ["delivery_id"])

    op.add_column("feature_flags", sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.sql.false()))
    op.add_column("feature_flags", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("feature_flags", sa.Column("archived_by", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("feature_flags", "archived_by")
    op.drop_column("feature_flags", "archived_at")
    op.drop_column("feature_flags", "archived")

    op.drop_index("ix_webhook_deliveries_delivery_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_project_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index("ix_deployments_webhook_delivery_id", table_name="deployments")
    op.drop_column("deployments", "webhook_delivery_id")
    op.drop_column("deployments", "failure_phase")
    op.drop_column("deployments", "last_heartbeat_at")
    op.drop_column("deployments", "lease_expires_at")

    op.drop_constraint("uq_projects_webhook_endpoint_id", "projects", type_="unique")
    op.drop_column("projects", "webhook_endpoint_id")
    op.drop_column("projects", "webhook_secret")
