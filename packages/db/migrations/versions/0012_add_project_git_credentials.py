"""add_project_git_credentials

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("git_credential_type", sa.String(length=32), nullable=False, server_default="none"))
        batch_op.add_column(sa.Column("git_credential_username", sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column("git_credential_token_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("git_credential_ssh_private_key_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("git_credential_ssh_known_hosts", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("git_credential_ssh_known_hosts")
        batch_op.drop_column("git_credential_ssh_private_key_encrypted")
        batch_op.drop_column("git_credential_token_encrypted")
        batch_op.drop_column("git_credential_username")
        batch_op.drop_column("git_credential_type")
