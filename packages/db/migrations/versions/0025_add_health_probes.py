"""Add additional HTTP probes and consecutive failure threshold."""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("healthcheck_urls", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("healthcheck_failure_threshold", sa.Integer(), nullable=False, server_default="2"))


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("healthcheck_failure_threshold")
        batch.drop_column("healthcheck_urls")
