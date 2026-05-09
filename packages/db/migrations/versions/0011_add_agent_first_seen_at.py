"""add_agent_first_seen_at

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_status") as batch_op:
        batch_op.add_column(sa.Column("agent_first_seen_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_status") as batch_op:
        batch_op.drop_column("agent_first_seen_at")
