"""add_deploy_safety_fields

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-22

"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("pre_deploy_command", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("post_deploy_command", sa.Text(), nullable=True))

    with op.batch_alter_table("deployments") as batch_op:
        batch_op.add_column(sa.Column("previous_commit_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("image_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("health_result", sa.JSON(), nullable=True))

    with op.batch_alter_table("deployment_targets") as batch_op:
        batch_op.add_column(sa.Column("target_commit_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("previous_commit_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("image_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("health_result", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("failure_phase", sa.String(length=32), nullable=True))

    with op.batch_alter_table("deployment_logs") as batch_op:
        batch_op.drop_constraint("uq_deployment_logs_deployment_seq", type_="unique")
        batch_op.create_unique_constraint(
            "uq_deployment_logs_target_seq",
            ["deployment_target_id", "seq"],
        )


def downgrade() -> None:
    with op.batch_alter_table("deployment_logs") as batch_op:
        batch_op.drop_constraint("uq_deployment_logs_target_seq", type_="unique")
        batch_op.create_unique_constraint(
            "uq_deployment_logs_deployment_seq",
            ["deployment_id", "seq"],
        )

    with op.batch_alter_table("deployment_targets") as batch_op:
        batch_op.drop_column("failure_phase")
        batch_op.drop_column("health_result")
        batch_op.drop_column("image_snapshot")
        batch_op.drop_column("previous_commit_hash")
        batch_op.drop_column("target_commit_hash")

    with op.batch_alter_table("deployments") as batch_op:
        batch_op.drop_column("health_result")
        batch_op.drop_column("image_snapshot")
        batch_op.drop_column("previous_commit_hash")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("post_deploy_command")
        batch_op.drop_column("pre_deploy_command")
