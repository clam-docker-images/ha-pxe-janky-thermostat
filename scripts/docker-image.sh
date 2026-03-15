#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
Usage:
  scripts/docker-image.sh build
  scripts/docker-image.sh publish

Environment:
  IMAGE_REPO     Image repository/name. Default: janky-thermostat
  IMAGE_TAG      Image tag. Default: latest
  IMAGE_PLATFORM Target platform. Default: linux/arm64
  BASE_IMAGE     Base image build arg. Default: debian:trixie-slim
  BUILDER_NAME   buildx builder name. Default: janky-thermostat-arm64
  EXTRA_ARGS     Extra arguments appended to docker buildx build
EOF
}

if [ "${1:-}" = "" ]; then
  usage >&2
  exit 64
fi

action=$1
case "${action}" in
  build|publish)
    ;;
  *)
    usage >&2
    exit 64
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but was not found in PATH" >&2
  exit 127
fi

if docker buildx version >/dev/null 2>&1; then
  BUILDX_CMD="docker buildx"
elif command -v docker-buildx >/dev/null 2>&1; then
  BUILDX_CMD="docker-buildx"
else
  cat >&2 <<'EOF'
docker buildx support was not found.

Install the buildx plugin or make the standalone docker-buildx binary available in PATH.
EOF
  exit 127
fi

IMAGE_REPO=${IMAGE_REPO:-janky-thermostat}
IMAGE_TAG=${IMAGE_TAG:-latest}
IMAGE_PLATFORM=${IMAGE_PLATFORM:-linux/arm64}
BASE_IMAGE=${BASE_IMAGE:-debian:trixie-slim}
BUILDER_NAME=${BUILDER_NAME:-janky-thermostat-arm64}
EXTRA_ARGS=${EXTRA_ARGS:-}
IMAGE_REF="${IMAGE_REPO}:${IMAGE_TAG}"

case "${IMAGE_REPO}" in
  *[ABCDEFGHIJKLMNOPQRSTUVWXYZ]*)
    cat >&2 <<EOF
IMAGE_REPO must be lowercase for Docker/OCI image references.

Received:
  ${IMAGE_REPO}

For GHCR, use the lowercase owner or org name in the image path, for example:
  ghcr.io/clam-/janky-thermostat
EOF
    exit 64
    ;;
esac

if ! printf '%s\n' "${IMAGE_REPO}" | grep -Eq '^[a-z0-9]+([._-][a-z0-9]+)*(\/[a-z0-9]+([._-][a-z0-9]+)*)*$'; then
  cat >&2 <<EOF
IMAGE_REPO is not a valid Docker/OCI image reference path.

Received:
  ${IMAGE_REPO}

Each slash-separated path component must use lowercase letters or digits, and may contain separators only between alphanumeric characters.
Examples of valid components:
  clam
  clam-io
  janky_thermostat

Examples of invalid components:
  clam-
  -clam
  clam--test
EOF
  exit 64
fi

ensure_builder() {
  if ! ${BUILDX_CMD} inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
    ${BUILDX_CMD} create \
      --name "${BUILDER_NAME}" \
      --driver docker-container \
      --use
  else
    ${BUILDX_CMD} use "${BUILDER_NAME}" >/dev/null
  fi

  ${BUILDX_CMD} inspect --bootstrap >/dev/null
}

run_build() {
  ensure_builder

  set -- \
    ${BUILDX_CMD} build \
    --builder "${BUILDER_NAME}" \
    --platform "${IMAGE_PLATFORM}" \
    --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
    --target runtime \
    --tag "${IMAGE_REF}"

  if [ "${action}" = "build" ]; then
    set -- "$@" --load
  else
    set -- "$@" --push
  fi

  if [ -n "${EXTRA_ARGS}" ]; then
    # shellcheck disable=SC2086
    set -- "$@" ${EXTRA_ARGS}
  fi

  set -- "$@" .

  echo "Building ${IMAGE_REF} for ${IMAGE_PLATFORM}" >&2
  if [ "${action}" = "publish" ]; then
    echo "Publishing ${IMAGE_REF}" >&2
  fi

  "$@"
}

run_build
