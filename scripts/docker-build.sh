#!/usr/bin/env bash
set -euo pipefail

# Docker Build and Optimization Script
# Builds optimized Docker images for the financial data analysis system

LOG() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] [DOCKER-BUILD] $*"; }

# Configuration
IMAGE_NAME="financial-data-analysis"
REGISTRY="${REGISTRY:-}"
VERSION="${VERSION:-latest}"
BUILD_ARGS="${BUILD_ARGS:-}"

# Determine full image name
if [[ -n "$REGISTRY" ]]; then
    FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$VERSION"
else
    FULL_IMAGE_NAME="$IMAGE_NAME:$VERSION"
fi

LOG "Building Docker image: $FULL_IMAGE_NAME"

# Build the Docker image with optimizations
docker build \
    --tag "$FULL_IMAGE_NAME" \
    --build-arg UV_VERSION=0.7.6 \
    $BUILD_ARGS \
    --compress \
    --no-cache \
    .

LOG "✅ Docker image built successfully: $FULL_IMAGE_NAME"

# Show image size
docker images "$FULL_IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

# Optional: Push to registry
if [[ -n "$REGISTRY" && "${PUSH_IMAGE:-false}" == "true" ]]; then
    LOG "Pushing image to registry..."
    docker push "$FULL_IMAGE_NAME"
    LOG "✅ Image pushed successfully"
fi

LOG "Build complete!"