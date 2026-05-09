"""add_project_audits

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False, server_default="update"),
        sa.Column("changed_by", sa.String(length=64), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("new_values", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_audits_project_id", "project_audits", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_audits_project_id", table_name="project_audits")
    op.drop_table("project_audits")
