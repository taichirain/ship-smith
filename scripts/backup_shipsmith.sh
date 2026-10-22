#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT}/docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-${ROOT}/.env.production}"
BACKUP_ROOT="${SHIPSMITH_BACKUP_DIR:-${ROOT}/backups}"
KEEP="${SHIPSMITH_BACKUP_RETENTION:-7}"
MIRROR_ROOT="${SHIPSMITH_BACKUP_MIRROR_DIR:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${BACKUP_ROOT}/${STAMP}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "missing env file: ${ENV_FILE}" >&2
  exit 1
fi

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

umask 077
mkdir -p "${BACKUP_DIR}"

echo "backing up ShipSmith PostgreSQL to ${BACKUP_DIR}"
compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${BACKUP_DIR}/shipsmith.dump"
compose exec -T postgres sh -c 'pg_dumpall -U "$POSTGRES_USER" --globals-only' > "${BACKUP_DIR}/shipsmith-globals.sql"

cat > "${BACKUP_DIR}/manifest.txt" <<EOF
created_at=$(date --iso-8601=seconds)
compose_file=${COMPOSE_FILE}
env_file=${ENV_FILE}
EOF

(
  cd "${BACKUP_DIR}"
  sha256sum ./*.dump ./*.sql > SHA256SUMS
)

echo "pruning old backups, keeping ${KEEP}"
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'   | sort -r   | tail -n "+$((KEEP + 1))"   | while read -r old; do
      echo "removing ${BACKUP_ROOT}/${old}"
      rm -rf -- "${BACKUP_ROOT:?}/${old}"
    done

if [[ -n "${MIRROR_ROOT}" ]]; then
  mkdir -p "${MIRROR_ROOT}"
  echo "mirroring to ${MIRROR_ROOT}/${STAMP}"
  rm -rf -- "${MIRROR_ROOT:?}/${STAMP}.tmp"
  if cp -a "${BACKUP_DIR}" "${MIRROR_ROOT}/${STAMP}.tmp"; then
    mv "${MIRROR_ROOT}/${STAMP}.tmp" "${MIRROR_ROOT}/${STAMP}"
  else
    echo "mirror failed; primary backup kept" >&2
    rm -rf -- "${MIRROR_ROOT:?}/${STAMP}.tmp"
  fi
fi

echo "backup complete: ${BACKUP_DIR}"
