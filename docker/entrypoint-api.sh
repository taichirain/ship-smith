#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running database migrations..."
cd /app/packages/db && alembic upgrade head
echo "Migrations complete."

echo "Starting ShipSmith API..."
exec uvicorn shipsmith_api.main:app --host 0.0.0.0 --port 8000
