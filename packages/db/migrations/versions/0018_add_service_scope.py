"""add_service_scope

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-25

"""
from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("service_scope", sa.String(length=16), nullable=False, server_default="app")
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("service_scope")
