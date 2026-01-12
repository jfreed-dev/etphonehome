#!/bin/bash
# =============================================================================
# ET Phone Home - Docker Test Suite
# =============================================================================
# Usage:
#   ./scripts/test_docker.sh              # Run all tests
#   ./scripts/test_docker.sh build        # Test builds only
#   ./scripts/test_docker.sh compose      # Test docker-compose only
#   ./scripts/test_docker.sh integration  # Test running containers
#   ./scripts/test_docker.sh lint         # Lint Dockerfiles only
#   ./scripts/test_docker.sh clean        # Clean up test artifacts
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/deploy/docker"
TEST_IMAGE_PREFIX="etphonehome-test"
COMPOSE_PROJECT="etphonehome-test"

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test() {
    echo -e "\n${GREEN}[TEST]${NC} $1"
}

pass_test() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((TESTS_PASSED++))
}

fail_test() {
    echo -e "  ${RED}✗${NC} $1"
    ((TESTS_FAILED++))
}

skip_test() {
    echo -e "  ${YELLOW}○${NC} $1 (skipped)"
    ((TESTS_SKIPPED++))
}

cleanup() {
    log_info "Cleaning up test artifacts..."

    # Stop and remove test containers
    docker ps -a --filter "name=${COMPOSE_PROJECT}" -q | xargs -r docker rm -f 2>/dev/null || true
    docker ps -a --filter "name=${TEST_IMAGE_PREFIX}" -q | xargs -r docker rm -f 2>/dev/null || true

    # Remove test images
    docker images --filter "reference=${TEST_IMAGE_PREFIX}*" -q | xargs -r docker rmi -f 2>/dev/null || true

    # Remove test networks
    docker network ls --filter "name=${COMPOSE_PROJECT}" -q | xargs -r docker network rm 2>/dev/null || true

    # Remove test volumes
    docker volume ls --filter "name=${COMPOSE_PROJECT}" -q | xargs -r docker volume rm 2>/dev/null || true

    log_info "Cleanup complete"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# =============================================================================
# Lint Tests
# =============================================================================

test_lint() {
    log_test "Dockerfile Linting"

    # Check if hadolint is available
    HADOLINT=""
    if command -v hadolint &> /dev/null; then
        HADOLINT="hadolint"
    elif [[ -f /tmp/hadolint ]]; then
        HADOLINT="/tmp/hadolint"
    else
        # Download hadolint
        log_info "Downloading hadolint..."
        wget -qO /tmp/hadolint https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64 2>/dev/null || {
            skip_test "Could not download hadolint"
            return
        }
        chmod +x /tmp/hadolint
        HADOLINT="/tmp/hadolint"
    fi

    HADOLINT_CONFIG="$DOCKER_DIR/.hadolint.yaml"
    HADOLINT_OPTS=""
    [[ -f "$HADOLINT_CONFIG" ]] && HADOLINT_OPTS="-c $HADOLINT_CONFIG"

    for dockerfile in "$DOCKER_DIR"/Dockerfile.* "$PROJECT_ROOT/web/Dockerfile"; do
        if [[ -f "$dockerfile" ]]; then
            if $HADOLINT $HADOLINT_OPTS "$dockerfile" 2>&1; then
                pass_test "$(basename "$dockerfile") passes lint"
            else
                fail_test "$(basename "$dockerfile") has lint errors"
            fi
        fi
    done

    # Lint docker-compose files with yamllint if available
    if command -v yamllint &> /dev/null || [[ -f "$PROJECT_ROOT/.venv/bin/yamllint" ]]; then
        YAMLLINT="${PROJECT_ROOT}/.venv/bin/yamllint"
        [[ ! -f "$YAMLLINT" ]] && YAMLLINT="yamllint"

        for compose_file in "$DOCKER_DIR"/docker-compose*.yml; do
            if [[ -f "$compose_file" ]]; then
                if $YAMLLINT -d "{extends: relaxed, rules: {line-length: {max: 120}}}" "$compose_file" 2>&1; then
                    pass_test "$(basename "$compose_file") passes yamllint"
                else
                    fail_test "$(basename "$compose_file") has yamllint errors"
                fi
            fi
        done
    else
        skip_test "yamllint not available for compose file linting"
    fi
}

# =============================================================================
# Build Tests
# =============================================================================

test_build_simple() {
    log_test "Building Dockerfile.simple"

    if docker build -t "${TEST_IMAGE_PREFIX}-simple:test" \
        -f "$DOCKER_DIR/Dockerfile.simple" \
        "$PROJECT_ROOT" 2>&1; then
        pass_test "Dockerfile.simple builds successfully"
    else
        fail_test "Dockerfile.simple build failed"
        return 1
    fi

    # Verify image exists and has expected labels/structure
    if docker image inspect "${TEST_IMAGE_PREFIX}-simple:test" &>/dev/null; then
        pass_test "Image was created"
    else
        fail_test "Image not found after build"
    fi

    # Check image size is reasonable (< 500MB)
    IMAGE_SIZE=$(docker image inspect "${TEST_IMAGE_PREFIX}-simple:test" --format '{{.Size}}')
    IMAGE_SIZE_MB=$((IMAGE_SIZE / 1024 / 1024))
    if [[ $IMAGE_SIZE_MB -lt 500 ]]; then
        pass_test "Image size is reasonable (${IMAGE_SIZE_MB}MB < 500MB)"
    else
        fail_test "Image size is too large (${IMAGE_SIZE_MB}MB >= 500MB)"
    fi
}

test_build_server() {
    log_test "Building Dockerfile.server"

    if docker build -t "${TEST_IMAGE_PREFIX}-server:test" \
        -f "$DOCKER_DIR/Dockerfile.server" \
        "$PROJECT_ROOT" 2>&1; then
        pass_test "Dockerfile.server builds successfully"
    else
        fail_test "Dockerfile.server build failed"
    fi
}

test_build_client() {
    log_test "Building Dockerfile.client"

    if docker build -t "${TEST_IMAGE_PREFIX}-client:test" \
        -f "$DOCKER_DIR/Dockerfile.client" \
        "$PROJECT_ROOT" 2>&1; then
        pass_test "Dockerfile.client builds successfully"
    else
        fail_test "Dockerfile.client build failed"
    fi
}

test_build_web() {
    log_test "Building web/Dockerfile"

    if [[ -f "$PROJECT_ROOT/web/Dockerfile" ]]; then
        if docker build -t "${TEST_IMAGE_PREFIX}-web:test" \
            "$PROJECT_ROOT/web" 2>&1; then
            pass_test "web/Dockerfile builds successfully"
        else
            fail_test "web/Dockerfile build failed"
        fi
    else
        skip_test "web/Dockerfile not found"
    fi
}

# =============================================================================
# Compose Tests
# =============================================================================

test_compose_config() {
    log_test "Docker Compose Configuration Validation"

    for compose_file in "$DOCKER_DIR"/docker-compose*.yml; do
        if [[ -f "$compose_file" ]]; then
            filename=$(basename "$compose_file")
            if docker compose -f "$compose_file" config --quiet 2>&1; then
                pass_test "$filename is valid"
            else
                fail_test "$filename has configuration errors"
            fi
        fi
    done
}

# =============================================================================
# Integration Tests
# =============================================================================

test_container_startup() {
    log_test "Container Startup Test"

    # Start the simple container
    CONTAINER_NAME="${TEST_IMAGE_PREFIX}-startup-test"

    # Remove if exists
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Run container
    if docker run -d \
        --name "$CONTAINER_NAME" \
        -e HOME=/data \
        "${TEST_IMAGE_PREFIX}-simple:test" 2>&1; then
        pass_test "Container started"
    else
        fail_test "Container failed to start"
        return 1
    fi

    # Wait for container to be running
    sleep 3

    # Check container is running
    if docker ps --filter "name=$CONTAINER_NAME" --filter "status=running" -q | grep -q .; then
        pass_test "Container is running"
    else
        fail_test "Container is not running"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    # Check health endpoint
    CONTAINER_IP=$(docker inspect "$CONTAINER_NAME" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
    if [[ -n "$CONTAINER_IP" ]]; then
        sleep 5  # Give server time to start
        if docker exec "$CONTAINER_NAME" curl -sf http://localhost:8765/health 2>&1; then
            pass_test "Health endpoint responds"
        else
            fail_test "Health endpoint not responding"
        fi
    else
        skip_test "Could not get container IP for health check"
    fi

    # Cleanup
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

test_container_healthcheck() {
    log_test "Container Health Check Test"

    CONTAINER_NAME="${TEST_IMAGE_PREFIX}-health-test"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Start container with health check
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e HOME=/data \
        --health-cmd="curl -f http://localhost:8765/health || exit 1" \
        --health-interval=5s \
        --health-timeout=3s \
        --health-retries=3 \
        --health-start-period=10s \
        "${TEST_IMAGE_PREFIX}-simple:test" 2>&1

    # Wait for health check to run
    log_info "Waiting for health checks..."
    for i in {1..12}; do
        sleep 5
        HEALTH=$(docker inspect "$CONTAINER_NAME" --format '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
        if [[ "$HEALTH" == "healthy" ]]; then
            pass_test "Container reports healthy status"
            docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
            return 0
        elif [[ "$HEALTH" == "unhealthy" ]]; then
            fail_test "Container reports unhealthy status"
            docker logs "$CONTAINER_NAME" 2>&1 | tail -10
            docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
            return 1
        fi
        echo "  Health status: $HEALTH (attempt $i/12)"
    done

    fail_test "Health check timed out"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

test_container_user() {
    log_test "Container User Permissions Test"

    CONTAINER_NAME="${TEST_IMAGE_PREFIX}-user-test"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Test running as non-root user
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e HOME=/data \
        "${TEST_IMAGE_PREFIX}-simple:test"

    sleep 2

    # Check process is not running as root
    PROC_USER=$(docker exec "$CONTAINER_NAME" id -u 2>/dev/null || echo "error")
    if [[ "$PROC_USER" != "0" && "$PROC_USER" != "error" ]]; then
        pass_test "Process runs as non-root user (UID: $PROC_USER)"
    else
        fail_test "Process is running as root or error getting user"
    fi

    # Test running as arbitrary UID (like in Kubernetes)
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    if docker run --rm \
        --user 1001:1001 \
        -e HOME=/data \
        --entrypoint python \
        "${TEST_IMAGE_PREFIX}-simple:test" \
        -c "print('Running as arbitrary UID')" 2>&1; then
        pass_test "Container can run as arbitrary UID"
    else
        fail_test "Container cannot run as arbitrary UID"
    fi

    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

test_container_volumes() {
    log_test "Container Volume Test"

    CONTAINER_NAME="${TEST_IMAGE_PREFIX}-volume-test"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Create temp directory for volume test
    TEMP_DIR=$(mktemp -d)
    chmod 777 "$TEMP_DIR"

    # Run container with volume mount
    docker run -d \
        --name "$CONTAINER_NAME" \
        -v "$TEMP_DIR:/data" \
        -e HOME=/data \
        "${TEST_IMAGE_PREFIX}-simple:test"

    sleep 3

    # Check that data directory is accessible
    if docker exec "$CONTAINER_NAME" test -w /data 2>/dev/null; then
        pass_test "Data directory is writable"
    else
        fail_test "Data directory is not writable"
    fi

    # Cleanup
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    rm -rf "$TEMP_DIR"
}

test_api_endpoints() {
    log_test "API Endpoint Tests"

    CONTAINER_NAME="${TEST_IMAGE_PREFIX}-api-test"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Start container
    docker run -d \
        --name "$CONTAINER_NAME" \
        -e HOME=/data \
        -p 18765:8765 \
        "${TEST_IMAGE_PREFIX}-simple:test"

    # Wait for startup
    log_info "Waiting for server to start..."
    for i in {1..30}; do
        if curl -sf http://localhost:18765/health &>/dev/null; then
            break
        fi
        sleep 1
    done

    # Test health endpoint
    if curl -sf http://localhost:18765/health | grep -q "healthy"; then
        pass_test "GET /health returns healthy"
    else
        fail_test "GET /health failed"
    fi

    # Test clients endpoint
    if curl -sf http://localhost:18765/clients | grep -q "clients"; then
        pass_test "GET /clients returns client list"
    else
        fail_test "GET /clients failed"
    fi

    # Test API dashboard
    if curl -sf http://localhost:18765/api/v1/dashboard | grep -q "server"; then
        pass_test "GET /api/v1/dashboard returns data"
    else
        fail_test "GET /api/v1/dashboard failed"
    fi

    # Cleanup
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}

# =============================================================================
# Main
# =============================================================================

print_summary() {
    echo ""
    echo "=============================================="
    echo "Docker Test Summary"
    echo "=============================================="
    echo -e "  ${GREEN}Passed:${NC}  $TESTS_PASSED"
    echo -e "  ${RED}Failed:${NC}  $TESTS_FAILED"
    echo -e "  ${YELLOW}Skipped:${NC} $TESTS_SKIPPED"
    echo "=============================================="

    if [[ $TESTS_FAILED -gt 0 ]]; then
        exit 1
    fi
}

run_all_tests() {
    test_lint
    test_build_simple
    test_build_server
    test_build_client
    test_build_web
    test_compose_config
    test_container_startup
    test_container_healthcheck
    test_container_user
    test_container_volumes
    test_api_endpoints
}

main() {
    cd "$PROJECT_ROOT"
    check_docker

    case "${1:-all}" in
        lint)
            test_lint
            ;;
        build)
            test_build_simple
            test_build_server
            test_build_client
            test_build_web
            ;;
        compose)
            test_compose_config
            ;;
        integration)
            test_build_simple  # Need image first
            test_container_startup
            test_container_healthcheck
            test_container_user
            test_container_volumes
            test_api_endpoints
            ;;
        clean)
            cleanup
            exit 0
            ;;
        all)
            run_all_tests
            ;;
        *)
            echo "Usage: $0 {all|lint|build|compose|integration|clean}"
            exit 1
            ;;
    esac

    print_summary
}

# Run cleanup on exit if tests fail
trap 'cleanup' EXIT

main "$@"
