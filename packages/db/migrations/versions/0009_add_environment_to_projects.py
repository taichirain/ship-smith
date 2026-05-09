"""add_environment_to_projects

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "environment",
            sa.String(length=16),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_projects_environment", table_name="projects")
    op.drop_column("projects", "environment")
