"""fix_alert_active_uniqueness

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-22

"""
from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

ACTIVE_PREDICATE = "status IN ('open', 'acknowledged')"


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.drop_constraint("uq_alerts_project_fingerprint_open", type_="unique")

    op.create_index(
        "uq_alerts_project_fingerprint_active",
        "alerts",
        ["project_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_PREDICATE),
        sqlite_where=sa.text(ACTIVE_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index("uq_alerts_project_fingerprint_active", table_name="alerts")
    with op.batch_alter_table("alerts") as batch_op:
        batch_op.create_unique_constraint(
            "uq_alerts_project_fingerprint_open",
            ["project_id", "fingerprint", "status"],
        )
