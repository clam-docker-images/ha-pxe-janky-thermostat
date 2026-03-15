#!/bin/sh
set -eu

if [ "${1:-}" = "--help" ]; then
  cat <<'EOF'
Usage: scripts/publish-image.sh <image-repo> [tag]

Compatibility wrapper around scripts/docker-image.sh publish.
Prefer:
  make image-publish IMAGE_REPO=<repo> IMAGE_TAG=<tag>
  sh scripts/docker-image.sh publish
EOF
  exit 0
fi

if [ "${1:-}" = "" ]; then
  echo "image repository is required" >&2
  exit 64
fi

IMAGE_REPO=$1
IMAGE_TAG=${2:-${IMAGE_TAG:-latest}}
export IMAGE_REPO IMAGE_TAG

exec sh scripts/docker-image.sh publish
