#!/usr/bin/env bash
# Pre-pull the base images a project's Dockerfiles reference.
#
# Why: the build host reaches the registry through a proxy that occasionally
# times out. Pulling the images up front (while the network is healthy) means
# a later `docker compose build` resolves every FROM line from the local image
# store instead of the registry.
#
# Usage: bash scripts/prewarm_project_images.sh <project workdir>
# Exit code is 0 even when one image fails; the failing names are printed.

set -uo pipefail

WORKDIR="${1:?usage: prewarm_project_images.sh <project workdir>}"

if [ ! -d "${WORKDIR}" ]; then
  echo "workdir not found: ${WORKDIR}" >&2
  exit 2
fi

echo "scanning ${WORKDIR} for Dockerfiles"
mapfile -t dockerfiles < <(find "${WORKDIR}" -maxdepth 4 -iname 'Dockerfile*' -type f 2>/dev/null)

if [ "${#dockerfiles[@]}" -eq 0 ]; then
  echo "no Dockerfiles found; nothing to prewarm"
  exit 0
fi

printf '  %s\n' "${dockerfiles[@]}"

# Stage names declared with AS, so they are not mistaken for registry images.
declare -A stages=()
for file in "${dockerfiles[@]}"; do
  while read -r stage; do
    stages["${stage,,}"]=1
  done < <(grep -hoiE '^FROM[[:space:]]+[^[:space:]]+[[:space:]]+AS[[:space:]]+[A-Za-z0-9._-]+' "${file}" \
            | awk '{print $4}')
done

declare -A images=()
frontend=0
for file in "${dockerfiles[@]}"; do
  if grep -qiE '^#[[:space:]]*syntax[[:space:]]*=[[:space:]]*docker/dockerfile' "${file}"; then
    frontend=1
  fi
  while read -r image; do
    [ -z "${image}" ] && continue
    key="${image,,}"
    [ "${key}" = "scratch" ] && continue
    [ -n "${stages[${key}]:-}" ] && continue
    # FROM may carry a digest or platform flag; keep the tag part only.
    images["${image}"]=1
  done < <(grep -hoiE '^FROM[[:space:]]+([^[:space:]]+[[:space:]]+AS[[:space:]]+[A-Za-z0-9._-]+|--platform=[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]+AS[[:space:]]+[A-Za-z0-9._-]+|[^[:space:]]+)' "${file}" \
            | awk '{print ($2 ~ /^--platform=/) ? $3 : $2}')
done

# The BuildKit frontend image is pulled by `# syntax=` directives, not by FROM.
if [ "${frontend}" -eq 1 ]; then
  images["docker/dockerfile:1"]=1
fi

if [ "${#images[@]}" -eq 0 ]; then
  echo "no base images to pull"
  exit 0
fi

echo
echo "pulling ${#images[@]} image(s)"
failed=()
for image in "${!images[@]}"; do
  if docker image inspect "${image}" >/dev/null 2>&1; then
    echo "  cached  ${image}"
    continue
  fi
  printf '  pull    %s ... ' "${image}"
  if timeout 300 docker pull "${image}" >/tmp/prewarm-pull.log 2>&1; then
    echo "ok"
  else
    echo "FAILED"
    tail -2 /tmp/prewarm-pull.log | sed 's/^/          /'
    failed+=("${image}")
  fi
done

echo
if [ "${#failed[@]}" -gt 0 ]; then
  echo "warning: ${#failed[@]} image(s) could not be pulled: ${failed[*]}"
  echo "a build that needs them will fail until the registry is reachable again"
  exit 1
fi
echo "all base images are available locally"
