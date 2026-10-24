#!/usr/bin/env bash
# Isolated Core smoke drill. Never points at an existing Compose project or volume.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRILL_DIR="$(mktemp -d "${TMPDIR:-/tmp}/shipsmith-drill.XXXXXXXX")"
PROJECT="shipsmith-drill-$(date +%s)-$$"
ENV_FILE="${DRILL_DIR}/.env.production"
COMPOSE_FILE="${ROOT}/docker-compose.prod.yml"
BACKUP_DIR="${DRILL_DIR}/backups"
API_CONTAINER=""

export COMPOSE_PROJECT_NAME="${PROJECT}"
export SHIPSMITH_ENV_FILE="${ENV_FILE}"

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" -p "${PROJECT}" "$@"
}

cleanup() {
  result=$?
  trap - EXIT
  if [[ -n "${API_CONTAINER}" ]]; then
    docker rm -f "${API_CONTAINER}" >/dev/null 2>&1 || true
  fi
  compose down -v --remove-orphans >/dev/null 2>&1 || true
  if [[ "${DRILL_DIR}" == "${TMPDIR:-/tmp}"/shipsmith-drill.* ]]; then
    rm -rf -- "${DRILL_DIR}"
  fi
  exit "${result}"
}
trap cleanup EXIT

umask 077
pg_password="$(openssl rand -hex 32)"
jwt_secret="$(openssl rand -hex 32)"
git_secret="$(openssl rand -hex 32)"
admin_password="$(openssl rand -hex 32)"

cat > "${ENV_FILE}" <<EOF
ENV=production
POSTGRES_USER=shipsmith
POSTGRES_PASSWORD=${pg_password}
POSTGRES_DB=shipsmith
JWT_SECRET_KEY=${jwt_secret}
GIT_CREDENTIALS_SECRET_KEY=${git_secret}
ADMIN_USERNAME=admin
ADMIN_PASSWORD=${admin_password}
CORS_ORIGINS=https://drill.invalid
PUBLIC_CORE_URL=https://drill.invalid
INSTALL_SCRIPT_URL=https://drill.invalid/install.sh
RUN_MIGRATIONS=0
EOF

echo "Isolated Compose project: ${PROJECT}"
compose config --quiet
compose build api
compose up -d postgres
compose run --rm api migrate
# A Compose one-off container does not publish the production API port.
API_CONTAINER="$(compose run -d --no-deps api)"

for _ in $(seq 1 30); do
  if docker exec "${API_CONTAINER}" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" \
    >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker exec "${API_CONTAINER}" python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

echo "== verify build tuning fields reach the Agent task payload =="
docker exec -i -e ADMIN_PASSWORD="${admin_password}" "${API_CONTAINER}" python - <<'PY'
import json
import os
import urllib.parse
import urllib.request

base = "http://127.0.0.1:8000/api/v1"


def call(path, method="GET", data=None, form=None, token=None):
    headers = {}
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode())


login = call(
    "/auth/login",
    method="POST",
    form={"username": "admin", "password": os.environ["ADMIN_PASSWORD"]},
)
admin_token = login["access_token"]

project = call(
    "/projects",
    method="POST",
    token=admin_token,
    data={
        "name": "drill-tuning",
        "git_repo": "https://example.invalid/drill/tuning.git",
        "git_branch": "main",
        "deploy_workdir": "/tmp/drill-tuning",
        "compose_file": "docker-compose.yml",
        "compose_service": "app",
        "deploy_strategy": "compose-build",
        "healthcheck_url": "http://127.0.0.1:8000/health",
        "healthcheck_timeout_seconds": 5,
        "healthcheck_expected_status": 200,
        "flags_file_path": "/tmp/drill-tuning/flags.json",
        "build_timeout_seconds": 5400,
        "pull_timeout_seconds": 1800,
        "build_no_cache": True,
    },
)
assert project["build_timeout_seconds"] == 5400
assert project["pull_timeout_seconds"] == 1800
assert project["build_no_cache"] is True

call(
    f"/projects/{project['id']}/deploy",
    method="POST",
    token=admin_token,
    data={"trigger_source": "manual"},
)

task_response = call("/agents/tasks", token=project["agent_token"])
task = task_response.get("task")
assert task is not None
assert task["build_timeout_seconds"] == 5400
assert task["pull_timeout_seconds"] == 1800
assert task["build_no_cache"] is True
print("build tuning fields verified in Agent task payload")
PY

COMPOSE_FILE="${COMPOSE_FILE}" ENV_FILE="${ENV_FILE}" \
  SHIPSMITH_BACKUP_DIR="${BACKUP_DIR}" SHIPSMITH_BACKUP_RETENTION=1 \
  "${ROOT}/scripts/backup_shipsmith.sh"
backup_path="$(find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -print -quit)"
if [[ -z "${backup_path}" ]]; then
  echo "backup was not created" >&2
  exit 1
fi
"${ROOT}/scripts/verify_shipsmith_backup.sh" "${backup_path}"
compose run --rm api migrate

echo "Core drill passed: build, migration, API health, build tuning payload, backup, isolated restore, repeat migration."
echo "This does not test an application rollback or the Agent outbox."
