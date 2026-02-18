#!/bin/bash
# Reach - Publish release to R2
# Wrapper script for publish_release_r2.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="${PROJECT_DIR}/.venv"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load environment from .env (check multiple locations)
for ENV_FILE in "${PROJECT_DIR}/deploy/docker/.env" "${PROJECT_DIR}/deploy/docker/secrets/.env"; do
    if [ -f "$ENV_FILE" ]; then
        echo -e "${YELLOW}Loading R2 configuration from ${ENV_FILE}${NC}"
        set -a
        # shellcheck source=/dev/null
        source "$ENV_FILE"
        set +a
        break
    fi
done

# Check for required R2 environment variables
if [ -z "$REACH_R2_ACCOUNT_ID" ] || [ -z "$REACH_R2_ACCESS_KEY" ] || \
   [ -z "$REACH_R2_SECRET_KEY" ] || [ -z "$REACH_R2_BUCKET" ]; then
    echo -e "${RED}Error: R2 environment variables not configured${NC}"
    echo ""
    echo "Required variables:"
    echo "  REACH_R2_ACCOUNT_ID"
    echo "  REACH_R2_ACCESS_KEY"
    echo "  REACH_R2_SECRET_KEY"
    echo "  REACH_R2_BUCKET"
    echo ""
    echo "Set these in deploy/docker/.env, deploy/docker/secrets/.env, or export them."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# Install boto3 if not present
if ! python3 -c "import boto3" 2>/dev/null; then
    echo -e "${YELLOW}Installing boto3...${NC}"
    pip install -q boto3
fi

# Run the Python script with all arguments
cd "$PROJECT_DIR"
python3 scripts/publish_release_r2.py "$@"
