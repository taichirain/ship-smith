"""add_migration_and_profiles

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-22

"""
from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("healthcheck_expected_status", sa.Integer(), nullable=False, server_default="200"))
        batch_op.add_column(sa.Column("migration_service", sa.String(length=128), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("migration_command", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("migration_timeout_seconds", sa.Integer(), nullable=False, server_default="600"))
        batch_op.add_column(sa.Column("migration_no_deps", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("compose_profiles", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("compose_profiles")
        batch_op.drop_column("migration_no_deps")
        batch_op.drop_column("migration_timeout_seconds")
        batch_op.drop_column("migration_command")
        batch_op.drop_column("migration_service")
        batch_op.drop_column("healthcheck_expected_status")
