#!/bin/bash
# ET Phone Home - Deploy builds to download server
# Uploads build artifacts and generates version manifest

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist"

# Server configuration (no defaults for host - must be set)
VPS_HOST="${PHONEHOME_VPS_HOST:-}"
VPS_USER="${PHONEHOME_VPS_USER:-root}"
VPS_KEY="${PHONEHOME_VPS_KEY:-$HOME/.ssh/id_ed25519}"
DEPLOY_DIR="/var/www/phonehome"

# Require VPS_HOST to be set
if [ -z "$VPS_HOST" ]; then
    echo "Error: PHONEHOME_VPS_HOST environment variable must be set"
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <version>"
    echo ""
    echo "Deploy build artifacts to the download server."
    echo ""
    echo "Arguments:"
    echo "  version    Version tag (e.g., v0.1.0)"
    echo ""
    echo "Environment variables:"
    echo "  PHONEHOME_VPS_HOST  Server hostname (required)"
    echo "  PHONEHOME_VPS_USER  SSH user (default: root)"
    echo "  PHONEHOME_VPS_KEY   SSH key path (default: ~/.ssh/id_ed25519)"
    exit 1
}

# Check arguments
VERSION="${1:-}"
if [ -z "$VERSION" ]; then
    usage
fi

# Strip 'v' prefix for directory name if present
VERSION_DIR="${VERSION#v}"

echo -e "${YELLOW}=== Deploying ET Phone Home $VERSION ===${NC}"
echo "Server: $VPS_USER@$VPS_HOST"
echo "Deploy directory: $DEPLOY_DIR"
echo ""

# Check for build artifacts
ARTIFACTS=(
    "phonehome-linux-x86_64.tar.gz"
    "phonehome-linux-aarch64.tar.gz"
    "phonehome-windows-amd64.zip"
)

echo "Checking build artifacts..."
for artifact in "${ARTIFACTS[@]}"; do
    if [ -f "$DIST_DIR/$artifact" ]; then
        echo -e "  ${GREEN}✓${NC} $artifact"
    else
        echo -e "  ${RED}✗${NC} $artifact (missing)"
    fi
done
echo ""

# Create version directory on server
echo "Creating directories on server..."
ssh -i "$VPS_KEY" "$VPS_USER@$VPS_HOST" "mkdir -p $DEPLOY_DIR/$VERSION_DIR $DEPLOY_DIR/latest"

# Upload artifacts
echo "Uploading artifacts..."
for artifact in "${ARTIFACTS[@]}"; do
    if [ -f "$DIST_DIR/$artifact" ]; then
        echo "  Uploading $artifact..."
        scp -i "$VPS_KEY" "$DIST_DIR/$artifact" "$VPS_USER@$VPS_HOST:$DEPLOY_DIR/$VERSION_DIR/"
        scp -i "$VPS_KEY" "$DIST_DIR/$artifact" "$VPS_USER@$VPS_HOST:$DEPLOY_DIR/latest/"
    fi
done

# Generate checksums
echo "Generating checksums..."
CHECKSUMS=""
for artifact in "${ARTIFACTS[@]}"; do
    if [ -f "$DIST_DIR/$artifact" ]; then
        sha256=$(sha256sum "$DIST_DIR/$artifact" | awk '{print $1}')
        size=$(stat -c%s "$DIST_DIR/$artifact" 2>/dev/null || stat -f%z "$DIST_DIR/$artifact")

        # Determine platform key
        case "$artifact" in
            *linux-x86_64*) platform="linux-x86_64" ;;
            *linux-aarch64*) platform="linux-aarch64" ;;
            *windows-amd64*) platform="windows-amd64" ;;
        esac

        CHECKSUMS="$CHECKSUMS
    \"$platform\": {
      \"url\": \"http://$VPS_HOST/latest/$artifact\",
      \"sha256\": \"$sha256\",
      \"size\": $size
    },"
    fi
done

# Remove trailing comma
CHECKSUMS="${CHECKSUMS%,}"

# Create version.json
echo "Creating version manifest..."
RELEASE_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
VERSION_JSON=$(cat <<EOF
{
  "version": "$VERSION_DIR",
  "release_date": "$RELEASE_DATE",
  "downloads": {$CHECKSUMS
  },
  "changelog": "See https://github.com/jfreed-dev/etphonehome/releases/tag/$VERSION"
}
EOF
)

echo "$VERSION_JSON" | ssh -i "$VPS_KEY" "$VPS_USER@$VPS_HOST" "cat > $DEPLOY_DIR/latest/version.json"
echo "$VERSION_JSON" | ssh -i "$VPS_KEY" "$VPS_USER@$VPS_HOST" "cat > $DEPLOY_DIR/$VERSION_DIR/version.json"

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Downloads available at:"
echo "  http://$VPS_HOST/latest/"
echo "  http://$VPS_HOST/$VERSION_DIR/"
echo ""
echo "Version manifest:"
echo "  http://$VPS_HOST/latest/version.json"
