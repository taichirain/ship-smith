# Served at /install.sh by the web app. Source of truth: packages/agent/install.sh
# Keep this copy in sync when the installer changes.
#!/usr/bin/env bash
set -euo pipefail

INSTANCE="${SHIPSMITH_INSTANCE:-default}"
INSTALL_DIR=""
CONFIG_DIR=""
SERVICE_NAME=""
AGENT_TOKEN=""
CORE_URL=""
WORKDIR=""
PROJECT_ID=""
AGENT_ID=""
DOWNLOAD_URL=""
LOCAL_FILE=""
GIT_URL=""
FORCE=0
NO_SYSTEMD=0

show_help() {
    cat <<'EOF'
ShipSmith Agent Installer

Usage:
  install.sh --token <token> --workdir <path> [options]

Required:
  -t, --token <token>       Agent token
  -w, --workdir <path>      Deploy work directory

Options:
  -u, --core-url <url>      Core API URL (default: http://localhost:8000/api/v1)
  -n, --instance <name>     Instance name (default: default)
      --name <name>         Alias for --instance
  -c, --config-dir <path>   Config directory (default: /etc/shipsmith/<instance>)
  -b, --bin-dir <path>      Binary directory (default: /usr/local/bin)
  -s, --service-name <name> systemd service name
      --project-id <id>     Optional project id stored in the env file
      --agent-id <id>       Optional agent id stored in the env file
  -d, --download <url>      Download the agent archive from a URL
  -f, --file <path>         Use a local agent binary or archive
  -g, --git-url <url>       pip-install the agent from a git URL
                            (default: gitee master; requires python3+git)
      --force               Replace this instance's binary/config/service only
      --no-systemd          Do not install or start a systemd service
  -h, --help                Show this help

Environment variables:
  SHIPSMITH_AGENT_TOKEN, SHIPSMITH_CORE_URL, SHIPSMITH_WORKDIR,
  SHIPSMITH_INSTANCE
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--token) AGENT_TOKEN="${2:-}"; shift 2 ;;
        -u|--core-url) CORE_URL="${2:-}"; shift 2 ;;
        -w|--workdir) WORKDIR="${2:-}"; shift 2 ;;
        -n|--instance|--name) INSTANCE="${2:-}"; shift 2 ;;
        -c|--config-dir) CONFIG_DIR="${2:-}"; shift 2 ;;
        -b|--bin-dir) INSTALL_DIR="${2:-}"; shift 2 ;;
        -s|--service-name) SERVICE_NAME="${2:-}"; shift 2 ;;
        --project-id) PROJECT_ID="${2:-}"; shift 2 ;;
        --agent-id) AGENT_ID="${2:-}"; shift 2 ;;
        -d|--download) DOWNLOAD_URL="${2:-}"; shift 2 ;;
        -f|--file) LOCAL_FILE="${2:-}"; shift 2 ;;
        -g|--git-url) GIT_URL="${2:-}"; shift 2 ;;
        --force) FORCE=1; shift ;;
        --no-systemd) NO_SYSTEMD=1; shift ;;
        -h|--help) show_help; exit 0 ;;
        *) echo "Unknown option: $1" >&2; show_help; exit 1 ;;
    esac
done

AGENT_TOKEN="${AGENT_TOKEN:-${SHIPSMITH_AGENT_TOKEN:-}}"
CORE_URL="${CORE_URL:-${SHIPSMITH_CORE_URL:-http://localhost:8000/api/v1}}"
WORKDIR="${WORKDIR:-${SHIPSMITH_WORKDIR:-}}"

case "${INSTANCE}" in
    *[!A-Za-z0-9._-]*|"")
        echo "Error: instance name may only contain letters, digits, dot, dash and underscore" >&2
        exit 1
        ;;
esac

if [ -z "${AGENT_TOKEN}" ]; then
    echo "Error: Agent token is required (--token or SHIPSMITH_AGENT_TOKEN)" >&2
    show_help
    exit 1
fi

if [ -z "${WORKDIR}" ]; then
    echo "Error: Work directory is required (--workdir or SHIPSMITH_WORKDIR)" >&2
    show_help
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    INSTALL_DIR="${INSTALL_DIR:-${HOME}/.local/bin}"
    CONFIG_DIR="${CONFIG_DIR:-${HOME}/.config/shipsmith/${INSTANCE}}"
else
    INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
    CONFIG_DIR="${CONFIG_DIR:-/etc/shipsmith/${INSTANCE}}"
fi
SERVICE_NAME="${SERVICE_NAME:-shipsmith-agent-${INSTANCE}}"
BINARY_PATH="${INSTALL_DIR}/shipsmith-agent-${INSTANCE}"
RUN_USER="${SUDO_USER:-$(id -un)}"

if [ -e "${CONFIG_DIR}/env" ] || [ -e "${BINARY_PATH}" ]; then
    if [ "${FORCE}" -ne 1 ]; then
        echo "Error: instance '${INSTANCE}' already exists at ${CONFIG_DIR}." >&2
        echo "Use --force to replace only this instance, or choose another --instance." >&2
        exit 1
    fi
fi

if [ "${NO_SYSTEMD}" -eq 0 ] && [ "$(id -u)" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
    if [ -e "/etc/systemd/system/${SERVICE_NAME}.service" ] && [ "${FORCE}" -ne 1 ]; then
        echo "Error: systemd service ${SERVICE_NAME}.service already exists." >&2
        echo "Use --force to replace only this instance, or choose another --service-name." >&2
        exit 1
    fi
fi

echo "========================================"
echo "ShipSmith Agent Installer"
echo "========================================"
echo "Instance:    ${INSTANCE}"
echo "Core URL:    ${CORE_URL}"
echo "Workdir:     ${WORKDIR}"
echo "Install dir: ${INSTALL_DIR}"
echo "Config dir:  ${CONFIG_DIR}"
echo ""

mkdir -p "${INSTALL_DIR}"
mkdir -p "${CONFIG_DIR}"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

if [ -n "${DOWNLOAD_URL}" ]; then
    echo "[1/4] Downloading agent..."
    curl -fsSL "${DOWNLOAD_URL}" -o "${TEMP_DIR}/shipsmith-agent.tar.gz"
    tar -xzf "${TEMP_DIR}/shipsmith-agent.tar.gz" -C "${TEMP_DIR}"
    BINARY="$(find "${TEMP_DIR}" -name "shipsmith-agent" -type f | head -1)"
elif [ -n "${LOCAL_FILE}" ]; then
    echo "[1/4] Using local file..."
    if [ "${LOCAL_FILE: -7}" = ".tar.gz" ]; then
        tar -xzf "${LOCAL_FILE}" -C "${TEMP_DIR}"
        BINARY="$(find "${TEMP_DIR}" -name "shipsmith-agent" -type f | head -1)"
    else
        BINARY="${LOCAL_FILE}"
    fi
else
    echo "[1/4] Checking for local build..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    BINARY="$(find "${SCRIPT_DIR}/dist" -name "shipsmith-agent" -type f | head -1 || true)"
fi

if [ -z "${BINARY:-}" ] || [ ! -f "${BINARY}" ]; then
    # No prebuilt binary available: install from source into a per-instance venv.
    GIT_URL="${GIT_URL:-${SHIPSMITH_AGENT_GIT_URL:-git+https://gitee.com/taichirain/ship-smith.git@master#subdirectory=packages/agent}}"
    echo "[1/4] No binary found; installing from source with pip..."
    command -v python3 >/dev/null 2>&1 || { echo "Error: python3 is required for source installs" >&2; exit 1; }
    command -v git >/dev/null 2>&1 || { echo "Error: git is required for source installs" >&2; exit 1; }
    python3 -m venv "${CONFIG_DIR}/venv"
    "${CONFIG_DIR}/venv/bin/pip" install -q --upgrade pip
    "${CONFIG_DIR}/venv/bin/pip" install "${GIT_URL}"
    BINARY_PATH="${CONFIG_DIR}/venv/bin/shipsmith-agent"
    echo "      installed to ${CONFIG_DIR}/venv"
else
    echo "[2/4] Installing binary for instance ${INSTANCE}..."
    cp "${BINARY}" "${BINARY_PATH}"
    chmod 755 "${BINARY_PATH}"
fi

if [ "${NO_SYSTEMD}" -eq 0 ] && [ "$(id -u)" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files "${SERVICE_NAME}.service" >/dev/null 2>&1; then
        systemctl stop "${SERVICE_NAME}.service" >/dev/null 2>&1 || true
    fi
fi

echo "[3/4] Writing configuration..."
cat > "${CONFIG_DIR}/env" <<EOF
# ShipSmith Agent Configuration
# Instance: ${INSTANCE}
# Auto-generated by install.sh

SHIPSMITH_CORE_URL=${CORE_URL}
SHIPSMITH_AGENT_TOKEN=${AGENT_TOKEN}
SHIPSMITH_WORKDIR=${WORKDIR}
SHIPSMITH_INSTANCE=${INSTANCE}
SHIPSMITH_PROJECT_ID=${PROJECT_ID}
SHIPSMITH_AGENT_ID=${AGENT_ID}

# Optional settings:
# SHIPSMITH_POLL_INTERVAL=30
# SHIPSMITH_HEARTBEAT_INTERVAL=30
# SHIPSMITH_FLAGS_INTERVAL=30
# SHIPSMITH_LOG_LEVEL=INFO
EOF
chmod 600 "${CONFIG_DIR}/env"

echo "[4/4] Configuring service..."
if [ "${NO_SYSTEMD}" -eq 0 ] && [ "$(id -u)" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=ShipSmith Agent (${INSTANCE})
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=${CONFIG_DIR}/env
ExecStart=${BINARY_PATH}
WorkingDirectory=/
User=${RUN_USER}
Restart=always
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now "${SERVICE_NAME}.service"
    echo ""
    echo "Service: ${SERVICE_NAME}.service"
    echo "Status:  systemctl status ${SERVICE_NAME}.service"
    echo "Logs:    journalctl -u ${SERVICE_NAME}.service -f"
else
    echo ""
    echo "Start the agent manually:"
    echo "  set -a; source ${CONFIG_DIR}/env; set +a"
    echo "  ${BINARY_PATH}"
    echo ""
    echo "Or install a systemd unit that uses:"
    echo "  EnvironmentFile=${CONFIG_DIR}/env"
    echo "  ExecStart=${BINARY_PATH}"
fi

echo ""
echo "Installation complete for instance: ${INSTANCE}"
