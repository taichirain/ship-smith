#!/usr/bin/env bash
# Build a ShipSmith image with a build-only proxy.
#
# PyPI and npm are unreachable directly from this host, and the proxy must not
# be put in ~/.docker/config.json (compose copies that into running containers)
# or in agents/*.env (compose copies that too). Passing it as build args keeps
# it inside the build and out of every container.
#
# Usage:
#   bash scripts/build_shipsmith_image.sh api            # tag = current short sha
#   bash scripts/build_shipsmith_image.sh web 1a2b3c4
#   bash scripts/build_shipsmith_image.sh all
#
# Override the proxy with BUILD_PROXY=... (set it to an empty string to disable).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-api}"
TAG="${2:-$(git -C "${ROOT}" rev-parse --short HEAD)}"
PROXY="${BUILD_PROXY-http://172.17.0.1:7891}"

proxy_args=()
if [ -n "${PROXY}" ] && timeout 2 bash -c "</dev/tcp/${PROXY#*://}" 2>/dev/null; then
  proxy_args=(
    --build-arg "HTTP_PROXY=${PROXY}"
    --build-arg "HTTPS_PROXY=${PROXY}"
    --build-arg "NO_PROXY=127.0.0.1,localhost,::1"
  )
  echo "building with proxy ${PROXY}"
else
  echo "building without proxy (${PROXY:-disabled} unreachable)"
fi

build() {
  local dockerfile="$1" image="$2"
  echo "==> ${image}:${TAG} (${dockerfile})"
  docker build "${proxy_args[@]}" -f "${ROOT}/${dockerfile}" -t "${image}:${TAG}" "${ROOT}" | tail -3
}

case "${TARGET}" in
  api) build docker/Dockerfile.api shipsmith-stage-api ;;
  web) build docker/Dockerfile.web shipsmith-stage-web ;;
  all)
    build docker/Dockerfile.api shipsmith-stage-api
    build docker/Dockerfile.web shipsmith-stage-web
    ;;
  *)
    echo "usage: $0 {api|web|all} [tag]" >&2
    exit 2
    ;;
esac

echo
echo "done: tag ${TAG}"
