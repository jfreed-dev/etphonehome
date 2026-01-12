#!/bin/bash
# Quick run ET Phone Home server container (without compose)
#
# Usage:
#   ./run-simple.sh                    # Run with defaults
#   ETPHONEHOME_API_KEY=xxx ./run-simple.sh  # Run with API key
#
set -e

CONTAINER_NAME="etphonehome-server"
IMAGE_NAME="etphonehome-server:latest"
PORT="${ETPHONEHOME_PORT:-8765}"

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' already exists."
    echo ""
    read -p "Remove and recreate? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rm -f "${CONTAINER_NAME}"
    else
        echo "Aborted. Use 'docker start ${CONTAINER_NAME}' to restart existing container."
        exit 1
    fi
fi

echo "Starting ${CONTAINER_NAME}..."
echo ""

docker run -d \
    --name "${CONTAINER_NAME}" \
    -p "${PORT}:8765" \
    -v etphonehome-data:/data \
    -v etphonehome-logs:/var/log/etphonehome \
    -e "ETPHONEHOME_API_KEY=${ETPHONEHOME_API_KEY:-}" \
    -e "ETPHONEHOME_LOG_LEVEL=${ETPHONEHOME_LOG_LEVEL:-INFO}" \
    -e "ETPHONEHOME_WEBHOOK_URL=${ETPHONEHOME_WEBHOOK_URL:-}" \
    --restart unless-stopped \
    "${IMAGE_NAME}"

echo ""
echo "Container started!"
echo ""
echo "Health check: curl http://localhost:${PORT}/health"
echo "Web UI:       http://localhost:${PORT}"
echo "Logs:         docker logs -f ${CONTAINER_NAME}"
echo ""
echo "Stop with:    docker stop ${CONTAINER_NAME}"
echo "Remove with:  docker rm ${CONTAINER_NAME}"
