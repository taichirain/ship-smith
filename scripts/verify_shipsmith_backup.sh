#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="${1:-}"
NAME="shipsmith-restore-check-$$"

if [[ -z "${BACKUP_DIR}" || ! -f "${BACKUP_DIR}/shipsmith.dump" ]]; then
  echo "usage: $0 <backup-directory-containing-shipsmith.dump>" >&2
  exit 2
fi

cleanup() {
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
}

if [[ ! -f "${BACKUP_DIR}/SHA256SUMS" ]]; then
  echo "missing SHA256SUMS: ${BACKUP_DIR}" >&2
  exit 1
fi
(cd "${BACKUP_DIR}" && sha256sum -c SHA256SUMS)
trap cleanup EXIT

docker run -d --name "${NAME}"   -e POSTGRES_PASSWORD=restore-check   -e POSTGRES_DB=shipsmith   postgres:16-alpine >/dev/null

for _ in $(seq 1 30); do
  if docker exec "${NAME}" pg_isready -U postgres >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker exec "${NAME}" pg_isready -U postgres >/dev/null 2>&1; then
  echo "restore-check PostgreSQL did not become ready" >&2
  exit 1
fi

docker cp "${BACKUP_DIR}/shipsmith.dump" "${NAME}:/tmp/shipsmith.dump"
docker exec "${NAME}" pg_restore -U postgres -d shipsmith   --no-owner --no-privileges --exit-on-error /tmp/shipsmith.dump

echo "restored table counts:"
docker exec "${NAME}" psql -U postgres -d shipsmith -Atc "
SELECT 'users=' || count(*) FROM users
UNION ALL SELECT 'projects=' || count(*) FROM projects
UNION ALL SELECT 'deployments=' || count(*) FROM deployments;
"

echo "backup restore check passed"
