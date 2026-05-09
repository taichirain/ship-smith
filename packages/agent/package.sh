#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${SCRIPT_DIR}/dist"
BUILD_DIR="${SCRIPT_DIR}/build"
VENV_DIR="${SCRIPT_DIR}/.venv"

VERSION=${1:-"0.1.0"}
OUTPUT_NAME="shipsmith-agent-v${VERSION}"

echo "========================================"
echo "ShipSmith Agent Package Script"
echo "Version: ${VERSION}"
echo "========================================"

echo ""
echo "[1/5] Cleaning up previous builds..."
rm -rf "${DIST_DIR}"
rm -rf "${BUILD_DIR}"
rm -rf "${SCRIPT_DIR}/shipsmith_agent.egg-info"
rm -rf "${PROJECT_ROOT}/packages/config/shipsmith_config.egg-info"
rm -rf "${PROJECT_ROOT}/packages/db/shipsmith_db.egg-info"
mkdir -p "${DIST_DIR}"

echo ""
echo "[2/5] Creating virtual environment..."
if [ -d "${VENV_DIR}" ]; then
    echo "Reusing existing venv..."
else
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

echo ""
echo "[3/5] Installing dependencies..."
pip install --upgrade pip
pip install pyinstaller

cd "${PROJECT_ROOT}"
pip install -e "${PROJECT_ROOT}/packages/config"
pip install -e "${PROJECT_ROOT}/packages/db"
pip install -e "${SCRIPT_DIR}"

echo ""
echo "[4/5] Building with PyInstaller..."
cd "${SCRIPT_DIR}"

cat > "${BUILD_DIR}/agent_entry.py" << 'EOF'
import sys
import os

packages_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "packages")
sys.path.insert(0, os.path.join(packages_dir, "config"))
sys.path.insert(0, os.path.join(packages_dir, "db"))
sys.path.insert(0, os.path.join(packages_dir, "agent"))

from shipsmith_agent.main import main

if __name__ == "__main__":
    main()
EOF

pyinstaller \
    --onefile \
    --name "shipsmith-agent" \
    --clean \
    --workpath "${BUILD_DIR}" \
    --distpath "${DIST_DIR}" \
    --specpath "${BUILD_DIR}" \
    --collect-all shipsmith_agent \
    --collect-all shipsmith_config \
    --collect-all shipsmith_db \
    --hidden-import pydantic \
    --hidden-import pydantic_core \
    --hidden-import httpx \
    --hidden-import psutil \
    --hidden-import yaml \
    "${BUILD_DIR}/agent_entry.py"

echo ""
echo "[5/5] Preparing distribution..."

ARCHIVE_NAME="${OUTPUT_NAME}-linux-x64.tar.gz"
TEMP_DIR="${DIST_DIR}/${OUTPUT_NAME}"

mkdir -p "${TEMP_DIR}"
mv "${DIST_DIR}/shipsmith-agent" "${TEMP_DIR}/"

cp "${PROJECT_ROOT}/shipsmith.yaml.example" "${TEMP_DIR}/shipsmith.yaml.example"
cp "${PROJECT_ROOT}/.env.example" "${TEMP_DIR}/env.example"

cat > "${TEMP_DIR}/README.txt" << 'EOF'
ShipSmith Agent
===============

Installation:
1. Copy shipsmith-agent to /usr/local/bin/
2. Create /etc/shipsmith/env with:
   SHIPSMITH_CORE_URL=https://your-core.example.com/api/v1
   SHIPSMITH_AGENT_TOKEN=<your-agent-token>
   SHIPSMITH_WORKDIR=/opt/your-project

Running:
  shipsmith-agent

Or with environment variables inline:
  SHIPSMITH_CORE_URL=... SHIPSMITH_AGENT_TOKEN=... SHIPSMITH_WORKDIR=... shipsmith-agent
EOF

cd "${DIST_DIR}"
tar -czvf "${ARCHIVE_NAME}" "${OUTPUT_NAME}"

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Output files:"
echo "  - ${DIST_DIR}/${ARCHIVE_NAME}"
echo "  - ${DIST_DIR}/${OUTPUT_NAME}/shipsmith-agent"
echo ""
echo "SHA256: $(sha256sum "${DIST_DIR}/${ARCHIVE_NAME}" | cut -d' ' -f1)"
