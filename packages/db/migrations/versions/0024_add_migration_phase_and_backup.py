"""add migration phase and pre-migration backup fields

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("migration_phase", sa.String(length=8), nullable=False, server_default="pre")
        )
        batch_op.add_column(
            sa.Column("migration_backup_service", sa.String(length=128), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("migration_backup_command", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("migration_backup_command")
        batch_op.drop_column("migration_backup_service")
        batch_op.drop_column("migration_phase")