"""add_project_runbook_fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-09

"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("release_notes_hint", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("troubleshooting_hint", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("admin_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("metrics_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("logs_url", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ssh_hint", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("ssh_hint")
        batch_op.drop_column("logs_url")
        batch_op.drop_column("metrics_url")
        batch_op.drop_column("admin_url")
        batch_op.drop_column("troubleshooting_hint")
        batch_op.drop_column("release_notes_hint")
        batch_op.drop_column("notes")
