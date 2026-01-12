#!/bin/bash
# Build the simplified ET Phone Home Docker image
#
# Usage:
#   ./build-simple.sh              # Build with default tag
#   ./build-simple.sh v0.1.10      # Build with version tag
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Get version tag from argument or use 'latest'
VERSION="${1:-latest}"

echo "Building etphonehome-server:${VERSION}..."
echo "Project root: ${PROJECT_ROOT}"

cd "$PROJECT_ROOT"

docker build \
    -t "etphonehome-server:${VERSION}" \
    -t "etphonehome-server:latest" \
    -f deploy/docker/Dockerfile.simple \
    .

echo ""
echo "Build complete!"
echo ""
echo "Image tags:"
docker images etphonehome-server --format "  {{.Repository}}:{{.Tag}} ({{.Size}})"
echo ""
echo "Run with:"
echo "  docker-compose -f deploy/docker/docker-compose.simple.yml up -d"
echo ""
echo "Or quick run:"
echo "  ./deploy/docker/run-simple.sh"
