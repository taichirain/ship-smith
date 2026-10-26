#!/usr/bin/env bash
# Create a new alembic migration skeleton with the next sequential number.
#
# Usage:
#   bash scripts/new_migration.sh "add index to orders"
#   bash scripts/new_migration.sh "backfill user tiers" --sql
#
# --sql seeds an op.execute() template for hand-written SQL; without it the
# skeleton uses batch_alter_table. Both live in the same versioned chain, so
# hand-written SQL becomes auditable and runs exactly once per database.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSIONS="${ROOT}/packages/db/migrations/versions"

if [ $# -lt 1 ]; then
  echo "usage: $0 <description words> [--sql]" >&2
  exit 2
fi

DESC="$1"
MODE="${2:-}"
SLUG="$(echo "${DESC}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/_/g; s/^_//; s/_$//')"
if [ -z "${SLUG}" ]; then
  echo "description must contain at least one letter or digit" >&2
  exit 2
fi

LAST="$(ls "${VERSIONS}" | grep -oE '^[0-9]{4}' | sort -n | tail -1)"
NEXT="$(printf '%04d' $((10#${LAST:-0} + 1)))"
FILE="${VERSIONS}/${NEXT}_${SLUG}.py"

if [ "${MODE}" = "--sql" ]; then
  BODY='    # Hand-written SQL goes here. It runs inside the migration
    # transaction, exactly once per database. Examples:
    # op.execute(sa.text("CREATE INDEX CONCURRENTLY ..."))
    # op.execute(sa.text("UPDATE orders SET tier = 1 WHERE tier IS NULL"))
    pass'
else
  BODY='    # batch_alter_table works on both PostgreSQL and SQLite.
    # batch_op.add_column(sa.Column("example", sa.String(length=64), nullable=True))
    pass'
fi

cat > "${FILE}" <<EOF
"""${DESC}

Revision ID: ${NEXT}
Revises: ${LAST}
"""
from alembic import op
import sqlalchemy as sa


revision = "${NEXT}"
down_revision = "${LAST}"
branch_labels = None
depends_on = None


def upgrade() -> None:
${BODY}


def downgrade() -> None:
    pass
EOF

echo "created ${FILE}"
echo "next: edit upgrade()/downgrade(), then run: cd packages/db && alembic upgrade head"