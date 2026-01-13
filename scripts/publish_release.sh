#!/bin/bash
# ET Phone Home - Publish release to R2
# Wrapper script for publish_release_r2.py

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load environment from .env if it exists
ENV_FILE="${PROJECT_DIR}/deploy/docker/.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}Loading R2 configuration from ${ENV_FILE}${NC}"
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

# Check for required R2 environment variables
if [ -z "$ETPHONEHOME_R2_ACCOUNT_ID" ] || [ -z "$ETPHONEHOME_R2_ACCESS_KEY" ] || \
   [ -z "$ETPHONEHOME_R2_SECRET_KEY" ] || [ -z "$ETPHONEHOME_R2_BUCKET" ]; then
    echo -e "${RED}Error: R2 environment variables not configured${NC}"
    echo ""
    echo "Required variables:"
    echo "  ETPHONEHOME_R2_ACCOUNT_ID"
    echo "  ETPHONEHOME_R2_ACCESS_KEY"
    echo "  ETPHONEHOME_R2_SECRET_KEY"
    echo "  ETPHONEHOME_R2_BUCKET"
    echo ""
    echo "Set these in ${ENV_FILE} or export them before running this script."
    exit 1
fi

# Run the Python script with all arguments
cd "$PROJECT_DIR"
python3 scripts/publish_release_r2.py "$@"
