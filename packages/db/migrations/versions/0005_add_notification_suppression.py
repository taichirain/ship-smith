"""add_notification_suppression

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_notification_settings") as batch_op:
        batch_op.add_column(
            sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="600")
        )
        batch_op.add_column(
            sa.Column("send_recovery", sa.Boolean(), nullable=False, server_default="true")
        )

    with op.batch_alter_table("notification_deliveries") as batch_op:
        batch_op.add_column(
            sa.Column("fingerprint", sa.String(length=256), nullable=True)
        )
        batch_op.add_column(
            sa.Column("is_recovery", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.add_column(
            sa.Column("is_suppressed", sa.Boolean(), nullable=False, server_default="false")
        )
        batch_op.create_index("ix_notification_deliveries_fingerprint", ["fingerprint"])


def downgrade() -> None:
    op.drop_index("ix_notification_deliveries_fingerprint", table_name="notification_deliveries")

    with op.batch_alter_table("notification_deliveries") as batch_op:
        batch_op.drop_column("is_suppressed")
        batch_op.drop_column("is_recovery")
        batch_op.drop_column("fingerprint")

    with op.batch_alter_table("project_notification_settings") as batch_op:
        batch_op.drop_column("send_recovery")
        batch_op.drop_column("cooldown_seconds")
