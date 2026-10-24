"""add_intentionally_stopped

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-25

"""
from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_status") as batch_op:
        batch_op.add_column(
            sa.Column("intentionally_stopped", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("project_status") as batch_op:
        batch_op.drop_column("intentionally_stopped")
