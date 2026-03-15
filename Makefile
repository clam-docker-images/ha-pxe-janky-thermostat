IMAGE_REPO ?= janky-thermostat
IMAGE_TAG ?= latest
IMAGE_PLATFORM ?= linux/arm64
BASE_IMAGE ?= debian:trixie-slim
BUILDER_NAME ?= janky-thermostat-arm64
EXTRA_ARGS ?=

.PHONY: image-build image-publish image-help

image-build:
	IMAGE_REPO='$(IMAGE_REPO)' \
	IMAGE_TAG='$(IMAGE_TAG)' \
	IMAGE_PLATFORM='$(IMAGE_PLATFORM)' \
	BASE_IMAGE='$(BASE_IMAGE)' \
	BUILDER_NAME='$(BUILDER_NAME)' \
	EXTRA_ARGS='$(EXTRA_ARGS)' \
	sh scripts/docker-image.sh build

image-publish:
	IMAGE_REPO='$(IMAGE_REPO)' \
	IMAGE_TAG='$(IMAGE_TAG)' \
	IMAGE_PLATFORM='$(IMAGE_PLATFORM)' \
	BASE_IMAGE='$(BASE_IMAGE)' \
	BUILDER_NAME='$(BUILDER_NAME)' \
	EXTRA_ARGS='$(EXTRA_ARGS)' \
	sh scripts/docker-image.sh publish

image-help:
	@printf '%s\n' \
	  'make image-build IMAGE_REPO=<repo> IMAGE_TAG=<tag>' \
	  'make image-publish IMAGE_REPO=<repo> IMAGE_TAG=<tag>' \
	  'Optional: IMAGE_PLATFORM=linux/arm64 BASE_IMAGE=debian:trixie-slim'
