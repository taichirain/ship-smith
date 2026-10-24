"""add explicit application service list

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("app_services", sa.JSON(), nullable=False, server_default="[]"))

    projects = sa.table(
        "projects",
        sa.column("id", sa.Integer()),
        sa.column("compose_service", sa.String()),
        sa.column("app_services", sa.JSON()),
    )
    connection = op.get_bind()
    for project_id, compose_service in connection.execute(
        sa.select(projects.c.id, projects.c.compose_service)
    ):
        connection.execute(
            projects.update().where(projects.c.id == project_id).values(app_services=[compose_service])
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("app_services")
