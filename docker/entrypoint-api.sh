#!/bin/bash
set -e

DB_DIR="${SHIPSMITH_DB_DIR:-/app/packages/db}"

if [ "${1:-}" = "migrate" ]; then
  echo "Waiting for PostgreSQL..."
  until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
    sleep 1
  done
  echo "Running database migrations..."
  cd "$DB_DIR" && exec alembic upgrade head
fi

echo "Waiting for PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Running database migrations..."
  cd "$DB_DIR" && alembic upgrade head
  echo "Migrations complete."
else
  echo "RUN_MIGRATIONS=0; skipping automatic migrations."
fi

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "Starting ShipSmith API..."
exec uvicorn shipsmith_api.main:app --host 0.0.0.0 --port 8000
