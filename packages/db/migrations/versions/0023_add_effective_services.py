"""snapshot the services used by a deployment

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.add_column(sa.Column("effective_services", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("effective_service_scope", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.drop_column("effective_service_scope")
        batch_op.drop_column("effective_services")
