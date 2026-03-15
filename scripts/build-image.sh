#!/bin/sh
set -eu

if [ "${1:-}" = "--help" ]; then
  cat <<'EOF'
Usage: scripts/build-image.sh [image-ref]

Compatibility wrapper around scripts/docker-image.sh build.
Prefer:
  make image-build
  sh scripts/docker-image.sh build
EOF
  exit 0
fi

if [ "${1:-}" != "" ]; then
  IMAGE_REPO=${1%:*}
  if [ "${IMAGE_REPO}" = "${1}" ]; then
    IMAGE_TAG=${IMAGE_TAG:-latest}
  else
    IMAGE_TAG=${1#*:}
  fi
  export IMAGE_REPO IMAGE_TAG
fi

if [ "${PLATFORM:-}" != "" ]; then
  IMAGE_PLATFORM=${PLATFORM}
  export IMAGE_PLATFORM
fi

exec sh scripts/docker-image.sh build
