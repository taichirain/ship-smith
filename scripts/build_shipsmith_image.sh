#!/usr/bin/env bash
# Build a ShipSmith image with selectable package mirrors and a build-only proxy.
#
# PyPI/npm/Debian mirrors are chosen from presets. "auto" (default) probes each
# preset with a short timeout and uses the first one that answers, so a dead
# mirror never stalls the build; if no mirror answers, it falls back to the
# official sources through the build proxy, exactly like before.
#
# Usage:
#   bash scripts/build_shipsmith_image.sh api            # tag = current short sha
#   bash scripts/build_shipsmith_image.sh web 1a2b3c4
#   bash scripts/build_shipsmith_image.sh all
#
# Overrides:
#   BUILD_MIRROR_PRESET=aliyun|tuna|tencent|official|proxy|auto (default auto)
#     aliyun/tuna/tencent: domestic mirror set (pip + apt; npm uses npmmirror)
#     official:            pypi.org / registry.npmjs.org / deb.debian.org, no proxy
#     proxy:               official sources through BUILD_PROXY
#   BUILD_PROXY=...        proxy URL for the "proxy" preset / fallback
#                          (empty string disables the proxy fallback)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-api}"
TAG="${2:-$(git -C "${ROOT}" rev-parse --short HEAD)}"
PROXY="${BUILD_PROXY-http://172.17.0.1:7891}"
PRESET="${BUILD_MIRROR_PRESET:-auto}"

# name|pip_index|npm_registry|apt_mirror|probe_url   (apt_mirror empty = image default)
PRESETS=(
  "aliyun|https://mirrors.aliyun.com/pypi/simple/|https://registry.npmmirror.com|mirrors.aliyun.com|https://mirrors.aliyun.com/pypi/simple/"
  "tuna|https://pypi.tuna.tsinghua.edu.cn/simple|https://registry.npmmirror.com|mirrors.tuna.tsinghua.edu.cn|https://pypi.tuna.tsinghua.edu.cn/simple/"
  "tencent|https://mirrors.cloud.tencent.com/pypi/simple/|https://registry.npmmirror.com|mirrors.cloud.tencent.com|https://mirrors.cloud.tencent.com/pypi/simple/"
  "official|https://pypi.org/simple|https://registry.npmjs.org||https://pypi.org/simple/"
)

probe() {  # probe <url> -> 0 if reachable within ~3s
  curl -sf --connect-timeout 2 --max-time 3 -o /dev/null "$1" 2>/dev/null
}

proxy_reachable() {
  [ -n "${PROXY}" ] && timeout 2 bash -c "</dev/tcp/${PROXY#*://}" 2>/dev/null
}

preset_fields() {  # preset_fields <name> -> sets PIP_INDEX NPM_REG APT_MIRR PROBE_URL
  local entry name
  for entry in "${PRESETS[@]}"; do
    name="${entry%%|*}"
    if [ "${name}" = "$1" ]; then
      IFS='|' read -r _ PIP_INDEX NPM_REG APT_MIRR PROBE_URL <<< "${entry}"
      return 0
    fi
  done
  return 1
}

# Resolve the effective strategy into: PIP_INDEX NPM_REG APT_MIRR USE_PROXY
resolve_strategy() {
  local name
  if [ "${PRESET}" = "proxy" ]; then
    PIP_INDEX=""; NPM_REG=""; APT_MIRR=""; USE_PROXY=1
    echo "strategy: proxy (${PROXY})"
    return 0
  fi
  if [ "${PRESET}" != "auto" ]; then
    if ! preset_fields "${PRESET}"; then
      echo "unknown BUILD_MIRROR_PRESET: ${PRESET}" >&2
      exit 2
    fi
    USE_PROXY=0
    echo "strategy: mirror preset ${PRESET} (manual)"
    return 0
  fi
  # auto: first reachable mirror wins
  for entry in "${PRESETS[@]}"; do
    name="${entry%%|*}"
    preset_fields "${name}"
    if probe "${PROBE_URL}"; then
      USE_PROXY=0
      echo "strategy: mirror preset ${name} (auto-detected)"
      return 0
    fi
    echo "preset ${name} unreachable, trying next..."
  done
  # fallback: official sources through the build proxy
  if proxy_reachable; then
    PIP_INDEX=""; NPM_REG=""; APT_MIRR=""; USE_PROXY=1
    echo "strategy: proxy fallback (${PROXY})"
    return 0
  fi
  PIP_INDEX=""; NPM_REG=""; APT_MIRR=""; USE_PROXY=0
  echo "strategy: image defaults (no mirror reachable, no proxy)"
}

resolve_strategy

# Stamp the release tag into the packages so the panel and every agent build
# report the exact version they were built from (e.g. 0.1.0+7a66225).
write_build_info() {
  echo "==> build stamp: ${TAG}"
  printf 'BUILD_SHA = "%s"\n' "${TAG}" > "${ROOT}/packages/agent/shipsmith_agent/_build_info.py"
  printf 'BUILD_SHA = "%s"\n' "${TAG}" > "${ROOT}/apps/api/shipsmith_api/_build_info.py"
}
write_build_info

build_agent_wheel() {
  # Bake the agent wheel into the web image so the panel can serve it at
  # /downloads/<wheel>. Installing from the panel guarantees the agent
  # version matches the panel version.
  local dest="${ROOT}/apps/web/public/downloads"
  local pip="${ROOT}/.venv/bin/pip"
  [ -x "${pip}" ] || pip="python3 -m pip"
  mkdir -p "${dest}"
  rm -f "${dest}"/shipsmith_agent-*.whl
  echo "==> building agent wheel into apps/web/public/downloads"
  ${pip} wheel --no-deps --no-build-isolation -w "${dest}" "${ROOT}/packages/agent" >/dev/null
  ls -1 "${dest}"
}

build() {
  local dockerfile="$1" image="$2"
  local args=(
    --build-arg "PIP_INDEX_URL=${PIP_INDEX}"
    --build-arg "NPM_REGISTRY=${NPM_REG}"
    --build-arg "APT_MIRROR=${APT_MIRR}"
  )
  if [ "${USE_PROXY}" = "1" ]; then
    args+=(
      --build-arg "HTTP_PROXY=${PROXY}"
      --build-arg "HTTPS_PROXY=${PROXY}"
      --build-arg "NO_PROXY=127.0.0.1,localhost,::1"
    )
  fi
  echo "==> ${image}:${TAG} (${dockerfile})"
  docker build "${args[@]}" -f "${ROOT}/${dockerfile}" -t "${image}:${TAG}" "${ROOT}" | tail -3
}

case "${TARGET}" in
  api) build docker/Dockerfile.api shipsmith-stage-api ;;
  agent)
    build docker/Dockerfile.agent shipsmith-stage-agent
    docker tag "shipsmith-stage-agent:${TAG}" shipsmith-stage-agent:latest
    ;;
  web)
    build_agent_wheel
    build docker/Dockerfile.web shipsmith-stage-web
    ;;
  all)
    build docker/Dockerfile.api shipsmith-stage-api
    build docker/Dockerfile.agent shipsmith-stage-agent
    docker tag "shipsmith-stage-agent:${TAG}" shipsmith-stage-agent:latest
    build_agent_wheel
    build docker/Dockerfile.web shipsmith-stage-web
    ;;
  *)
    echo "usage: $0 {api|web|agent|all} [tag]" >&2
    exit 2
    ;;
esac

echo
echo "done: tag ${TAG}"