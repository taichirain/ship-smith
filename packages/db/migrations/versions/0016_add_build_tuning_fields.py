"""add_build_tuning_fields

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-24

"""
from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("build_timeout_seconds", sa.Integer(), nullable=False, server_default="1800"))
        batch_op.add_column(sa.Column("pull_timeout_seconds", sa.Integer(), nullable=False, server_default="900"))
        batch_op.add_column(sa.Column("build_no_cache", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("build_no_cache")
        batch_op.drop_column("pull_timeout_seconds")
        batch_op.drop_column("build_timeout_seconds")
