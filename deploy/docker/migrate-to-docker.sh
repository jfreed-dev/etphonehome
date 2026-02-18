#!/bin/bash
# Reach - Docker Migration Script
#
# This script helps migrate from systemd service to Docker container.
# It reads settings from /etc/reach/server.env and uses existing client data.
#
# Usage:
#   ./migrate-to-docker.sh start    # Stop systemd, start Docker
#   ./migrate-to-docker.sh stop     # Stop Docker, start systemd
#   ./migrate-to-docker.sh status   # Show current status
#   ./migrate-to-docker.sh logs     # View Docker logs
#   ./migrate-to-docker.sh build    # Rebuild Docker image
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONTAINER_NAME="reach-server"
IMAGE_NAME="reach-server:latest"
SYSTEMD_SERVICE="reach-mcp"
SERVER_ENV="/etc/reach/server.env"
CLIENT_DATA_DIR="${HOME}/.reach-server"
PORT="${REACH_PORT:-8765}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Load environment from server.env
load_env() {
    if [[ -f "$SERVER_ENV" ]]; then
        log_info "Loading settings from $SERVER_ENV"
        # Export non-comment lines as environment variables
        set -a
        # shellcheck source=/dev/null
        source <(grep -v '^#' "$SERVER_ENV" | grep -v '^$' | sed 's/^/export /')
        set +a
    else
        log_warn "Server config not found at $SERVER_ENV"
        log_warn "Using defaults or environment variables"
    fi
}

# Check if systemd service is running
is_systemd_running() {
    systemctl is-active --quiet "$SYSTEMD_SERVICE" 2>/dev/null
}

# Check if Docker container is running
is_docker_running() {
    docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"
}

# Check if Docker container exists (running or stopped)
docker_container_exists() {
    docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"
}

# Check if Docker image exists
docker_image_exists() {
    docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -q "^${IMAGE_NAME}$"
}

# Stop systemd service
stop_systemd() {
    if is_systemd_running; then
        log_info "Stopping systemd service: $SYSTEMD_SERVICE"
        sudo systemctl stop "$SYSTEMD_SERVICE"
        sleep 2
        if is_systemd_running; then
            log_error "Failed to stop systemd service"
            return 1
        fi
        log_info "Systemd service stopped"
    else
        log_info "Systemd service already stopped"
    fi
}

# Start systemd service
start_systemd() {
    if ! is_systemd_running; then
        log_info "Starting systemd service: $SYSTEMD_SERVICE"
        sudo systemctl start "$SYSTEMD_SERVICE"
        sleep 3
        if is_systemd_running; then
            log_info "Systemd service started"
        else
            log_error "Failed to start systemd service"
            return 1
        fi
    else
        log_info "Systemd service already running"
    fi
}

# Build Docker image
build_docker() {
    log_info "Building Docker image: $IMAGE_NAME"
    cd "$PROJECT_ROOT"
    docker build \
        -t "$IMAGE_NAME" \
        -f deploy/docker/Dockerfile.simple \
        . || {
            log_error "Docker build failed"
            return 1
        }
    log_info "Docker image built successfully"
    docker images "$IMAGE_NAME" --format "  Size: {{.Size}}"
}

# Start Docker container
start_docker() {
    load_env

    # Check if image exists
    if ! docker_image_exists; then
        log_warn "Docker image not found, building..."
        build_docker || return 1
    fi

    # Remove existing container if it exists
    if docker_container_exists; then
        log_info "Removing existing container"
        docker rm -f "$CONTAINER_NAME" >/dev/null
    fi

    # Ensure client data directory exists
    mkdir -p "$CLIENT_DATA_DIR"

    # Get current user's UID/GID for permission compatibility
    HOST_UID=$(id -u)
    HOST_GID=$(id -g)

    log_info "Starting Docker container: $CONTAINER_NAME"
    log_info "  - Port: $PORT"
    log_info "  - Data: $CLIENT_DATA_DIR"
    log_info "  - User: $HOST_UID:$HOST_GID"

    docker run -d \
        --name "$CONTAINER_NAME" \
        --user "${HOST_UID}:${HOST_GID}" \
        -p "${PORT}:8765" \
        -v "${CLIENT_DATA_DIR}:/data" \
        -e "REACH_API_KEY=${REACH_API_KEY:-}" \
        -e "REACH_LOG_LEVEL=${REACH_LOG_LEVEL:-INFO}" \
        -e "REACH_WEBHOOK_URL=${REACH_WEBHOOK_URL:-}" \
        -e "REACH_R2_ACCOUNT_ID=${REACH_R2_ACCOUNT_ID:-}" \
        -e "REACH_R2_ACCESS_KEY=${REACH_R2_ACCESS_KEY:-}" \
        -e "REACH_R2_SECRET_KEY=${REACH_R2_SECRET_KEY:-}" \
        -e "REACH_R2_BUCKET=${REACH_R2_BUCKET:-}" \
        -e "REACH_R2_REGION=${REACH_R2_REGION:-auto}" \
        --restart unless-stopped \
        "$IMAGE_NAME" >/dev/null

    sleep 3

    if is_docker_running; then
        log_info "Docker container started"

        # Wait for health check
        log_info "Waiting for health check..."
        for _ in {1..10}; do
            if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
                log_info "Health check passed!"
                curl -s "http://localhost:${PORT}/health" | python3 -m json.tool 2>/dev/null || true
                return 0
            fi
            sleep 1
        done
        log_warn "Health check timeout - container may still be starting"
    else
        log_error "Failed to start Docker container"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi
}

# Stop Docker container
stop_docker() {
    if is_docker_running; then
        log_info "Stopping Docker container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME" >/dev/null
        log_info "Docker container stopped"
    else
        log_info "Docker container not running"
    fi

    if docker_container_exists; then
        log_info "Removing container"
        docker rm "$CONTAINER_NAME" >/dev/null
    fi
}

# Show status
show_status() {
    echo ""
    echo "=== Reach Status ==="
    echo ""

    # Systemd service status
    if is_systemd_running; then
        echo -e "Systemd service ($SYSTEMD_SERVICE): ${GREEN}RUNNING${NC}"
    else
        echo -e "Systemd service ($SYSTEMD_SERVICE): ${YELLOW}STOPPED${NC}"
    fi

    # Docker container status
    if is_docker_running; then
        echo -e "Docker container ($CONTAINER_NAME): ${GREEN}RUNNING${NC}"
        docker ps --filter name="$CONTAINER_NAME" --format "  Image: {{.Image}}, Uptime: {{.Status}}"
    elif docker_container_exists; then
        echo -e "Docker container ($CONTAINER_NAME): ${YELLOW}STOPPED${NC}"
    else
        echo -e "Docker container ($CONTAINER_NAME): ${YELLOW}NOT CREATED${NC}"
    fi

    # Docker image
    if docker_image_exists; then
        echo -e "Docker image ($IMAGE_NAME): ${GREEN}EXISTS${NC}"
        docker images "$IMAGE_NAME" --format "  Size: {{.Size}}, Created: {{.CreatedSince}}"
    else
        echo -e "Docker image ($IMAGE_NAME): ${YELLOW}NOT BUILT${NC}"
    fi

    # Port status
    echo ""
    echo "Port $PORT:"
    if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
        ss -tlnp 2>/dev/null | grep ":${PORT} " | head -1
    else
        echo "  Not listening"
    fi

    # Health check
    echo ""
    if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
        echo -e "Health endpoint: ${GREEN}RESPONDING${NC}"
        curl -s "http://localhost:${PORT}/health" 2>/dev/null
    else
        echo -e "Health endpoint: ${YELLOW}NOT RESPONDING${NC}"
    fi
    echo ""
}

# Show Docker logs
show_logs() {
    if docker_container_exists; then
        docker logs -f "$CONTAINER_NAME"
    else
        log_error "Container $CONTAINER_NAME does not exist"
        exit 1
    fi
}

# Main command handling
case "${1:-}" in
    start)
        log_info "Switching to Docker..."
        stop_systemd
        start_docker
        show_status
        ;;
    stop)
        log_info "Switching back to systemd..."
        stop_docker
        start_systemd
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    build)
        build_docker
        ;;
    *)
        echo "Reach - Docker Migration Script"
        echo ""
        echo "Usage: $0 {start|stop|status|logs|build}"
        echo ""
        echo "Commands:"
        echo "  start   - Stop systemd service, start Docker container"
        echo "  stop    - Stop Docker container, start systemd service"
        echo "  status  - Show current status of both"
        echo "  logs    - View Docker container logs (follow)"
        echo "  build   - Build/rebuild Docker image"
        echo ""
        echo "Configuration:"
        echo "  Server config:  $SERVER_ENV"
        echo "  Client data:    $CLIENT_DATA_DIR"
        echo "  Docker image:   $IMAGE_NAME"
        echo "  Container:      $CONTAINER_NAME"
        exit 1
        ;;
esac
